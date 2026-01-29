# -*- coding: utf-8 -*-
"""Agent Hook

通过 HTTP POST 将 Agent 消息回传到 Server（增量推送模式，线程池执行）
"""
from typing import Any, Dict
import asyncio
from concurrent.futures import ThreadPoolExecutor

import httpx
from agentscope.agent import AgentBase


# 创建一个全局线程池（在整个程序生命周期内复用）
_http_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hook_http")

# 全局字典，用于存储每个 reply_id 的最后发送内容
_last_sent_content: Dict[str, str] = {}

# 全局字典，用于存储每个 reply_id 的消息序列号
_message_sequence: Dict[str, int] = {}


class AgentHooks:
    """
Agent 钩子管理类
    
    实现增量消息推送，使用线程池避免阻塞 Agent 主线程。
    """
    
    # 类级属性，存储配置
    url: str = ""
    reply_id: str = ""
    
    @classmethod
    def _sync_push_to_studio(cls, payload: Dict[str, Any]) -> None:
        """
        同步版本的推送函数，供线程池调用
        
        Args:
            payload: 要推送的数据
        """
        if not cls.url or not cls.reply_id:
            return
        
        n_retry = 0
        while n_retry < 3:
            try:
                # 使用 httpx 的同步客户端
                with httpx.Client(timeout=5.0) as client:
                    response = client.post(
                        f"{cls.url}/trpc/pushMessageToChatAgent",
                        json=payload,
                    )
                    response.raise_for_status()
                    break
            except Exception as e:
                n_retry += 1
                if n_retry >= 3:
                    print(f"[Hook Error] 推送消息失败: {e}")
                    break
    
    @classmethod
    def _sync_push_finished_signal(cls, reply_id: str) -> None:
        """
        同步版本的完成信号推送，供线程池调用
        
        Args:
            reply_id: 回复 ID
        """
        if not cls.url or not reply_id:
            return
        
        n_retry = 0
        while n_retry < 3:
            try:
                with httpx.Client(timeout=5.0) as client:
                    response = client.post(
                        f"{cls.url}/trpc/pushFinishedSignalToChatAgent",
                        json={"replyId": reply_id},
                    )
                    response.raise_for_status()
                    
                    # 清理该 reply_id 的状态
                    if reply_id in _last_sent_content:
                        del _last_sent_content[reply_id]
                    if reply_id in _message_sequence:
                        del _message_sequence[reply_id]
                    break
            except Exception as e:
                n_retry += 1
                if n_retry >= 3:
                    print(f"[Hook Error] 发送完成信号失败: {e}")
                    break
    
    @classmethod
    def pre_print_hook(cls, agent: AgentBase, kwargs: dict[str, Any]) -> None:
        """
        Agent 输出前的钩子，将增量消息转发到 Server
        
        使用线程池执行 HTTP 请求，不阻塞 Agent 主线程。
        
        Args:
            agent: Agent 实例
            kwargs: 包含 msg 的字典
        """
        msg = kwargs["msg"]
        
        # 获取当前完整回复内容
        current_content = ""
        content_blocks = msg.get_content_blocks()
        
        if isinstance(content_blocks, list):
            # 处理多模态消息，只提取文本
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    current_content += block.get("text", "")
        elif isinstance(content_blocks, str):
            current_content = content_blocks
        
        # 获取当前 reply_id
        reply_id = cls.reply_id
        if not reply_id:
            return
        
        # 获取并递增序列号
        if reply_id not in _message_sequence:
            _message_sequence[reply_id] = 0
        sequence = _message_sequence[reply_id]
        _message_sequence[reply_id] += 1
        
        # 计算增量内容
        last_content = _last_sent_content.get(reply_id, "")
        
        if current_content.startswith(last_content):
            # 计算增量
            delta_content = current_content[len(last_content):]
            _last_sent_content[reply_id] = current_content
        else:
            # 如果不匹配（例如新消息），则发送全部，并重置状态
            delta_content = current_content
            _last_sent_content[reply_id] = current_content
        
        # 如果没有增量，则不发送
        if not delta_content:
            return
        
        # 构建只包含增量内容的新消息
        message_data = msg.to_dict()
        message_data["content"] = [{"type": "text", "text": delta_content}]
        # 添加序列号保证顺序
        message_data["sequence"] = sequence
        payload = {
            "replyId": reply_id,
            "msg": message_data
        }
        
        # 关键修改：提交到线程池，不阻塞主线程
        try:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                _http_executor,
                cls._sync_push_to_studio,
                payload
            )
        except RuntimeError:
            # 如果没有事件循环，直接在线程池中执行
            _http_executor.submit(cls._sync_push_to_studio, payload)
    
    @classmethod
    def post_reply_hook(cls, agent: AgentBase, *args, **kwargs) -> None:
        """
        Agent 回复完成后的钩子，发送完成信号到 Server
        
        使用线程池执行，不阻塞主线程。
        
        Args:
            agent: Agent 实例
        """
        reply_id = cls.reply_id
        if not reply_id:
            return
        
        # 提交到线程池执行
        try:
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                _http_executor,
                cls._sync_push_finished_signal,
                reply_id
            )
        except RuntimeError:
            _http_executor.submit(cls._sync_push_finished_signal, reply_id)


# 便捷函数，兼容原有调用方式
def studio_pre_print_hook(agent: AgentBase, kwargs: dict[str, Any]) -> None:
    """pre_print 钩子函数（增量推送模式，线程池执行）"""
    AgentHooks.pre_print_hook(agent, kwargs)


def studio_post_reply_hook(agent: AgentBase, *args, **kwargs) -> None:
    """post_reply 钩子函数"""
    AgentHooks.post_reply_hook(agent, *args, **kwargs)
