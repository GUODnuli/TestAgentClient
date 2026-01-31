# -*- coding: utf-8 -*-
"""Agent Hook

通过 HTTP POST 将 Agent 消息回传到 Server（结构化事件推送模式，线程池执行）
"""
from typing import Any, Dict, List, Set
import asyncio
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
from agentscope.agent import AgentBase


# 创建一个全局线程池（在整个程序生命周期内复用）
_http_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="hook_http")

# 全局字典，用于存储每个 reply_id 的最后发送内容（文本增量计算）
_last_sent_content: Dict[str, str] = {}

# 全局字典，用于存储每个 reply_id 的消息序列号
_message_sequence: Dict[str, int] = {}

# 全局字典，用于追踪已发送的 tool_use id（去重）
_sent_tool_ids: Dict[str, Set[str]] = {}

# 全局字典，用于追踪已发送的 tool_result id（去重）
_sent_tool_result_ids: Dict[str, Set[str]] = {}

# 线程锁，保护全局可变状态（主线程写入，线程池清理）
_state_lock = threading.Lock()


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
                    with _state_lock:
                        _last_sent_content.pop(reply_id, None)
                        _message_sequence.pop(reply_id, None)
                        _sent_tool_ids.pop(reply_id, None)
                        _sent_tool_result_ids.pop(reply_id, None)
                    break
            except Exception as e:
                n_retry += 1
                if n_retry >= 3:
                    print(f"[Hook Error] 发送完成信号失败: {e}")
                    break
    
    @classmethod
    def _next_sequence(cls, reply_id: str) -> int:
        """获取并递增序列号（调用方需持有 _state_lock）"""
        if reply_id not in _message_sequence:
            _message_sequence[reply_id] = 0
        seq = _message_sequence[reply_id]
        _message_sequence[reply_id] += 1
        return seq

    @classmethod
    def _submit_payload(cls, payload: Dict[str, Any]) -> None:
        """提交 payload 到线程池，不阻塞主线程"""
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(
                _http_executor,
                cls._sync_push_to_studio,
                payload
            )
        except RuntimeError:
            _http_executor.submit(cls._sync_push_to_studio, payload)

    @classmethod
    def pre_print_hook(cls, agent: AgentBase, kwargs: dict[str, Any]) -> None:
        """
        Agent 输出前的钩子，将结构化事件转发到 Server

        遍历 content_blocks，对 text 块计算增量，对 tool_use/tool_result 块去重后发送。
        所有事件打包为 events 数组，一次 HTTP POST 推送。

        Args:
            agent: Agent 实例
            kwargs: 包含 msg 的字典
        """
        msg = kwargs["msg"]
        reply_id = cls.reply_id
        if not reply_id:
            return

        content_blocks = msg.get_content_blocks()

        # 收集当前所有文本（在锁外完成，无需访问共享状态）
        current_text = ""
        if isinstance(content_blocks, list):
            for block in content_blocks:
                if isinstance(block, dict) and block.get("type") == "text":
                    current_text += block.get("text", "")
        elif isinstance(content_blocks, str):
            current_text = content_blocks

        events: List[Dict[str, Any]] = []

        # 加锁保护全局可变状态
        with _state_lock:
            # 初始化去重集合
            if reply_id not in _sent_tool_ids:
                _sent_tool_ids[reply_id] = set()
            if reply_id not in _sent_tool_result_ids:
                _sent_tool_result_ids[reply_id] = set()

            # 计算文本增量
            last_content = _last_sent_content.get(reply_id, "")
            if current_text.startswith(last_content):
                delta_text = current_text[len(last_content):]
            else:
                delta_text = current_text
            _last_sent_content[reply_id] = current_text

            # 生成文本增量事件
            if delta_text:
                events.append({
                    "type": "text",
                    "content": delta_text,
                    "sequence": cls._next_sequence(reply_id),
                })

            # 提取 tool_use 和 tool_result 事件
            if isinstance(content_blocks, list):
                for block in content_blocks:
                    if not isinstance(block, dict):
                        continue

                    block_type = block.get("type", "")

                    if block_type == "tool_use":
                        tool_id = block.get("id", "")
                        if tool_id and tool_id not in _sent_tool_ids[reply_id]:
                            _sent_tool_ids[reply_id].add(tool_id)
                            tool_input = block.get("input", {})
                            if not isinstance(tool_input, (dict, list, str)):
                                try:
                                    tool_input = json.loads(str(tool_input))
                                except (json.JSONDecodeError, TypeError, ValueError):
                                    tool_input = str(tool_input)
                            events.append({
                                "type": "tool_call",
                                "id": tool_id,
                                "name": block.get("name", "unknown"),
                                "input": tool_input,
                                "sequence": cls._next_sequence(reply_id),
                            })

                    elif block_type == "tool_result":
                        tool_id = block.get("tool_use_id", "") or block.get("id", "")
                        if tool_id and tool_id not in _sent_tool_result_ids[reply_id]:
                            _sent_tool_result_ids[reply_id].add(tool_id)
                            output = block.get("content", block.get("output", ""))
                            if isinstance(output, list):
                                output = " ".join(
                                    item.get("text", str(item))
                                    for item in output
                                    if isinstance(item, dict)
                                ) or str(output)
                            events.append({
                                "type": "tool_result",
                                "id": tool_id,
                                "name": block.get("name", ""),
                                "output": str(output) if not isinstance(output, str) else output,
                                "success": not block.get("is_error", False),
                                "sequence": cls._next_sequence(reply_id),
                            })

        # 没有任何事件则跳过
        if not events:
            return

        payload = {
            "replyId": reply_id,
            "events": events,
        }

        cls._submit_payload(payload)
    
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
            loop = asyncio.get_running_loop()
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
