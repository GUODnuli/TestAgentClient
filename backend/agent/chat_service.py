# -*- coding: utf-8 -*-
"""
ChatService - 聊天服务

管理 Agent 子进程、接收 Hook 回传、广播消息到前端。
"""
import asyncio
import json
import subprocess
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, AsyncGenerator

from backend.common.logger import get_logger
from backend.common.database import Database
from backend.common.config import ModelConfig

logger = get_logger()


class ReplyingStateManager:
    """回复状态管理器（单例）"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._replying = False
            cls._instance._current_conversation_id = None
        return cls._instance
    
    def set_replying(self, replying: bool, conversation_id: str = None):
        self._replying = replying
        self._current_conversation_id = conversation_id if replying else None
    
    def is_replying(self) -> bool:
        return self._replying
    
    def get_state(self) -> Dict[str, Any]:
        return {
            "replying": self._replying,
            "conversation_id": self._current_conversation_id
        }


class MessageQueue:
    """消息队列，用于 SSE 流式返回"""
    
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
    
    def create(self, reply_id: str) -> asyncio.Queue:
        """创建消息队列"""
        queue = asyncio.Queue()
        self._queues[reply_id] = queue
        return queue
    
    def get(self, reply_id: str) -> Optional[asyncio.Queue]:
        """获取消息队列"""
        return self._queues.get(reply_id)
    
    def remove(self, reply_id: str):
        """移除消息队列"""
        if reply_id in self._queues:
            del self._queues[reply_id]
    
    async def put(self, reply_id: str, message: Dict):
        """向队列推送消息"""
        queue = self._queues.get(reply_id)
        if queue:
            await queue.put(message)


class AgentProcessManager:
    """
Agent 子进程管理器
    
    负责启动和管理 Agent 子进程，并记录其输出到日志。
    """
    
    def __init__(self):
        self._processes: Dict[str, subprocess.Popen] = {}
        # 确保 logs 目录存在
        self._logs_dir = Path("logs")
        self._logs_dir.mkdir(exist_ok=True)
    
    def _log_stream(self, stream, stream_name: str, conversation_id: str):
        """
        读取子进程输出流并记录到文件
        
        Args:
            stream: stdout 或 stderr 流
            stream_name: 流名称（'stdout' 或 'stderr'）
            conversation_id: 会话 ID
        """
        log_file = self._logs_dir / f"agent_{conversation_id}.log"
        
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"[{datetime.now().isoformat()}] {stream_name} output:\n")
                f.write(f"{'='*60}\n")
                
                for line in stream:
                    if line:
                        # 同时记录到文件和后端日志
                        f.write(line)
                        f.flush()
                        logger.info(f"[Agent {conversation_id[:8]}] {stream_name}: {line.strip()}")
        except Exception as e:
            logger.error(f"[AgentProcess] 读取 {stream_name} 失败: {e}")
    
    def start_agent(
        self,
        conversation_id: str,
        reply_id: str,
        query: str,
        studio_url: str,
        llm_provider: str,
        model_name: str,
        api_key: str,
        write_permission: bool = False,
        client_kwargs: Dict = None,
        generate_kwargs: Dict = None,
    ) -> subprocess.Popen:
        """
        启动 Agent 子进程
        
        Args:
            conversation_id: 会话 ID
            reply_id: 回复 ID
            query: 用户查询（JSON 格式）
            studio_url: Server URL
            llm_provider: LLM 提供商
            model_name: 模型名称
            api_key: API Key
            write_permission: 是否有写权限
            client_kwargs: 客户端额外参数
            generate_kwargs: 生成额外参数
            
        Returns:
            Popen 进程对象
        """
        # Agent 脚本路径
        agent_script = Path(__file__).parent / "main.py"
        
        # query 已经是 JSON 字符串，直接通过 stdin 传递
        query_json = query
        
        # 构建命令参数（query 从 stdin 读取）
        args = [
            sys.executable,  # Python 解释器
            str(agent_script),
            "--query-from-stdin",  # 标记从 stdin 读取 query
            "--studio_url", studio_url,
            "--conversation_id", conversation_id,
            "--reply_id", reply_id,
            "--llmProvider", llm_provider,
            "--modelName", model_name,
            "--apiKey", api_key,
            "--writePermission", str(write_permission).lower(),
        ]
        
        if client_kwargs:
            args.extend(["--clientKwargs", json.dumps(client_kwargs)])
        if generate_kwargs:
            args.extend(["--generateKwargs", json.dumps(generate_kwargs)])
        
        logger.info(f"[AgentProcess] 启动 Agent: {' '.join(args[:5])}...")
        logger.info(f"[AgentProcess] query_json 长度: {len(query_json)} 字符")
        
        # 准备环境变量（Windows 上强制使用 UTF-8 编码）
        import os
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        # 启动子进程（query 通过 stdin 传递）
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding="utf-8",
            errors="replace",
            env=env,  # 使用修改后的环境变量
            cwd=str(Path(__file__).parent.parent.parent),  # 项目根目录
        )
        
        # 启动线程读取 stdout 和 stderr
        stdout_thread = threading.Thread(
            target=self._log_stream,
            args=(process.stdout, "stdout", conversation_id),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=self._log_stream,
            args=(process.stderr, "stderr", conversation_id),
            daemon=True
        )
        stdout_thread.start()
        stderr_thread.start()
        
        logger.info(f"[AgentProcess] 已启动输出读取线程")
        
        # 将 query JSON 写入 stdin
        try:
            process.stdin.write(query_json + "\n")
            process.stdin.flush()
            process.stdin.close()  # 关闭 stdin，告诉子进程数据已写完
            logger.info(f"[AgentProcess] 已写入 query 到 stdin")
        except Exception as e:
            logger.error(f"[AgentProcess] 写入 stdin 失败: {e}")
        
        self._processes[conversation_id] = process
        return process
    
    def stop_agent(self, conversation_id: str) -> bool:
        """停止 Agent 子进程"""
        process = self._processes.get(conversation_id)
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            del self._processes[conversation_id]
            return True
        return False
    
    def is_running(self, conversation_id: str) -> bool:
        """检查 Agent 是否运行中"""
        process = self._processes.get(conversation_id)
        if process:
            return process.poll() is None
        return False
    
    def cleanup(self):
        """清理所有子进程"""
        for conv_id in list(self._processes.keys()):
            self.stop_agent(conv_id)


class ChatService:
    """
    聊天服务
    
    管理 Agent 子进程、存储消息、广播到前端。
    """
    
    def __init__(
        self,
        database: Database,
        model_config: Optional[ModelConfig] = None,
        socket_manager = None,  # SocketManager 实例，由 agent_service 传入
    ):
        """
        初始化聊天服务
        
        Args:
            database: 数据库实例
            model_config: 模型配置
            socket_manager: Socket.IO 管理器
        """
        self.database = database
        self.model_config = model_config
        self.socket_manager = socket_manager
        
        self.process_manager = AgentProcessManager()
        self.replying_state = ReplyingStateManager()
        self.message_queue = MessageQueue()  # SSE 消息队列
        
        # 存储待广播的消息
        self._pending_replies: Dict[str, Dict] = {}
        
        logger.info("[ChatService] 初始化完成（子进程模式）")
    
    def set_socket_manager(self, socket_manager):
        """设置 Socket.IO 管理器（延迟注入）"""
        self.socket_manager = socket_manager
    
    async def send_message(
        self,
        message: str,
        user_id: str,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        发送消息（启动 Agent 子进程）
        
        Args:
            message: 用户消息
            user_id: 用户 ID
            conversation_id: 会话 ID
            
        Returns:
            响应字典
        """
        # 创建或获取会话 ID
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            # 创建数据库会话
            self.database.create_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                title=message[:50]
            )
        
        # 创建回复 ID
        reply_id = str(uuid.uuid4())
        
        # 保存用户消息
        user_message_id = str(uuid.uuid4())
        self.database.create_message(
            message_id=user_message_id,
            conversation_id=conversation_id,
            role="user",
            content=message
        )
        
        # 设置回复状态
        self.replying_state.set_replying(True, conversation_id)
        
        # 广播回复状态
        if self.socket_manager:
            await self.socket_manager.broadcast_replying_state(
                self.replying_state.get_state()
            )
        
        # 初始化待处理回复
        self._pending_replies[reply_id] = {
            "conversation_id": conversation_id,
            "reply_id": reply_id,
            "messages": [],
            "finished": False,
        }
        
        # 获取模型配置
        llm_provider = "dashscope"
        model_name = "qwen3-max-preview"
        api_key = ""
        
        if self.model_config:
            model_name = self.model_config.model_name or model_name
            api_key = self.model_config.api_key or api_key
        
        # 获取 Server URL
        studio_url = "http://localhost:8000"
        
        # 构建查询 JSON
        query = json.dumps([{"type": "text", "text": message}])
        
        # 启动 Agent 子进程
        self.process_manager.start_agent(
            conversation_id=conversation_id,
            reply_id=reply_id,
            query=query,
            studio_url=studio_url,
            llm_provider=llm_provider,
            model_name=model_name,
            api_key=api_key,
        )
        
        return {
            "conversation_id": conversation_id,
            "reply_id": reply_id,
            "status": "processing",
            "timestamp": datetime.now().isoformat(),
        }
    
    async def send_message_streaming(
        self,
        message: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        uploaded_files: Optional[List[str]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        发送消息并流式返回（SSE 兼容）
        
        通过消息队列接收 Agent 回传的中间消息并流式返回给前端。
        """
        # 创建或获取会话 ID
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            self.database.create_conversation(
                conversation_id=conversation_id,
                user_id=user_id,
                title=message[:50]
            )
        
        # 创建回复 ID
        reply_id = str(uuid.uuid4())
        
        # 保存用户消息
        user_message_id = str(uuid.uuid4())
        self.database.create_message(
            message_id=user_message_id,
            conversation_id=conversation_id,
            role="user",
            content=message
        )
        
        # 设置回复状态
        self.replying_state.set_replying(True, conversation_id)
        
        # 创建消息队列
        queue = self.message_queue.create(reply_id)
        
        # 初始化待处理回复
        self._pending_replies[reply_id] = {
            "conversation_id": conversation_id,
            "reply_id": reply_id,
            "messages": [],
            "finished": False,
        }
        
        # 返回启动信息
        yield {
            "type": "start",
            "conversation_id": conversation_id,
            "reply_id": reply_id,
        }
        
        # 获取模型配置
        llm_provider = "dashscope"
        model_name = "qwen3-max-preview"
        api_key = ""
        
        if self.model_config:
            llm_provider = getattr(self.model_config, 'provider', llm_provider)
            model_name = getattr(self.model_config, 'model_name', model_name)
            api_key = getattr(self.model_config, 'api_key', api_key)
        
        # 获取 Server URL
        studio_url = "http://localhost:8000"
        
        # 构建查询 JSON（使用文本块格式传递上下文）
        query_blocks = []
        
        # 添加系统上下文块（包含 user_id、conversation_id 和文件信息）
        if uploaded_files:
            files_info = ", ".join(uploaded_files)
            context_text = f"""[SYSTEM CONTEXT]
user_id: {user_id}
conversation_id: {conversation_id}
uploaded_files: {files_info}
[/SYSTEM CONTEXT]"""
        else:
            context_text = f"""[SYSTEM CONTEXT]
user_id: {user_id}
conversation_id: {conversation_id}
uploaded_files: (none)
[/SYSTEM CONTEXT]"""
        
        query_blocks.append({"type": "text", "text": context_text})
        
        # 添加用户消息
        query_blocks.append({"type": "text", "text": message})
        
        query = json.dumps(query_blocks)
        
        # 启动 Agent 子进程
        self.process_manager.start_agent(
            conversation_id=conversation_id,
            reply_id=reply_id,
            query=query,
            studio_url=studio_url,
            llm_provider=llm_provider,
            model_name=model_name,
            api_key=api_key,
        )
        
        # 从消息队列读取并返回中间消息
        try:
            while True:
                try:
                    # 等待消息，超时 30 秒
                    msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    if msg is None:  # 结束信号
                        break
                    
                    yield msg
                    
                except asyncio.TimeoutError:
                    # 检查进程是否还在运行
                    if not self.process_manager.is_running(conversation_id):
                        break
                    # 发送心跳
                    yield {"type": "heartbeat"}
        finally:
            # 清理消息队列
            self.message_queue.remove(reply_id)
            self.replying_state.set_replying(False)
        
        # 返回完成信息
        yield {
            "type": "done",
            "conversation_id": conversation_id,
            "timestamp": datetime.now().isoformat(),
        }
    
    async def handle_agent_message(self, reply_id: str, msg: Dict[str, Any]):
        """
        处理来自 Agent 的消息（由 Hook 端点调用）
        
        Args:
            reply_id: 回复 ID
            msg: 消息数据（包含 sequence 序列号）
        """
        reply_data = self._pending_replies.get(reply_id)
        if not reply_data:
            logger.warning(f"[ChatService] 未找到回复记录: {reply_id}")
            return
        
        conversation_id = reply_data["conversation_id"]
        
        # 直接处理消息，不进行复杂的序列号排序
        # 由于 Hook 是在线程池中并发发送，但 HTTP 请求本身是顺序到达的
        # 即使有小幅度乱序，也不会影响阅读体验
        await self._process_message_content(reply_id, msg, conversation_id)
    
    async def _process_message_content(self, reply_id: str, msg: Dict[str, Any], conversation_id: str):
        """
        处理单个消息的内容（按顺序调用）
        
        Args:
            reply_id: 回复 ID
            msg: 消息数据
            conversation_id: 会话 ID
        """
        reply_data = self._pending_replies.get(reply_id)
        if not reply_data:
            return
        
        # 解析消息内容
        content = msg.get("content", "")
        thinking_content = ""
        text_content = ""
        
        # 如果 content 是列表，提取不同类型的内容
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_content += block.get("text", "")
                    elif block.get("type") == "thinking":
                        thinking_content += block.get("thinking", "")
        elif isinstance(content, str):
            text_content = content
        
        # 检测并解析测试用例（从工具返回的 JSON）
        await self._extract_and_push_testcases(reply_id, text_content, conversation_id)
        
        # 获取或初始化该 message_id 的累积内容
        message_id = msg.get("id", str(uuid.uuid4()))
        
        # 检查是否已有该消息（用于累积增量内容）
        existing_index = None
        for i, existing_msg in enumerate(reply_data["messages"]):
            if existing_msg.get("id") == message_id:
                existing_index = i
                break
        
        if existing_index is not None:
            # 更新现有消息：累积内容
            existing_msg = reply_data["messages"][existing_index]
            existing_content = existing_msg.get("_accumulated_content", "")
            new_accumulated_content = existing_content + text_content
            
            # 更新消息
            existing_msg["_accumulated_content"] = new_accumulated_content
            existing_msg["content"] = [{"type": "text", "text": new_accumulated_content}]
        else:
            # 新消息：初始化累积内容
            msg["_accumulated_content"] = text_content
            reply_data["messages"].append(msg)
        
        # 构建 SSE 事件并推送到消息队列（推送增量内容）
        if thinking_content:
            await self.message_queue.put(reply_id, {
                "type": "thinking",
                "content": thinking_content
            })
        
        if text_content:
            await self.message_queue.put(reply_id, {
                "type": "chunk",
                "content": text_content
            })
        
        # 同时广播到 Socket.IO（广播增量）
        if self.socket_manager:
            await self.socket_manager.broadcast_message(
                conversation_id=conversation_id,
                reply_id=reply_id,
                message=msg  # 这里发送的是增量消息
            )
    
    async def handle_agent_finished(self, reply_id: str):
        """
        处理 Agent 完成信号（由 Hook 端点调用）
        
        Args:
            reply_id: 回复 ID
        """
        reply_data = self._pending_replies.get(reply_id)
        if reply_data:
            reply_data["finished"] = True
            conversation_id = reply_data["conversation_id"]
            
            # 保存累积内容到数据库
            for msg in reply_data["messages"]:
                accumulated_content = msg.get("_accumulated_content", "")
                if accumulated_content:
                    message_id = msg.get("id", str(uuid.uuid4()))
                    try:
                        self.database.create_message(
                            message_id=message_id,
                            conversation_id=conversation_id,
                            role="assistant",
                            content=accumulated_content
                        )
                        logger.info(f"[ChatService] 保存完整消息 | message_id: {message_id} | 长度: {len(accumulated_content)}")
                    except Exception as e:
                        # 如果消息已存在，尝试更新
                        if "已存在" in str(e) or "exists" in str(e).lower():
                            logger.warning(f"[ChatService] 消息已存在，跳过: {message_id}")
                        else:
                            logger.error(f"[ChatService] 保存消息失败: {e}")
            
            # 清理进程
            self.process_manager.stop_agent(conversation_id)
        
        # 发送结束信号到消息队列
        await self.message_queue.put(reply_id, None)
        
        # 重置回复状态
        self.replying_state.set_replying(False)
        
        # 广播状态到 Socket.IO
        if self.socket_manager:
            await self.socket_manager.broadcast_replying_state(
                self.replying_state.get_state()
            )
            await self.socket_manager.broadcast_finished(reply_id)
    
    async def _extract_and_push_testcases(self, reply_id: str, text_content: str, conversation_id: str):
        """
        从文本内容中提取测试用例 JSON 并推送到前端
        
        Args:
            reply_id: 回复 ID
            text_content: 文本内容（可能包含 JSON）
            conversation_id: 会话 ID
        """
        if not text_content or len(text_content) < 100:
            return
        
        # 检测是否包含测试用例关键字
        testcase_keywords = [
            '"testcases"',
            '"interface_name"',
            'generate_positive_cases',
            'generate_negative_cases',
            'generate_security_cases'
        ]
        
        if not any(keyword in text_content for keyword in testcase_keywords):
            return
        
        try:
            # 尝试解析 JSON
            import re
            # 查找 JSON 对象（以 { 开头，以 } 结尾）
            json_match = re.search(r'\{.*"testcases".*\}', text_content, re.DOTALL)
            if not json_match:
                return
            
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            # 提取测试用例列表
            testcases = data.get("testcases", [])
            if not testcases or not isinstance(testcases, list):
                return
            
            # 统计信息
            count = data.get("count", len(testcases))
            status = data.get("status", "unknown")
            
            # 推送测试用例到前端
            await self.message_queue.put(reply_id, {
                "type": "testcases",
                "data": {
                    "status": status,
                    "count": count,
                    "testcases": testcases
                }
            })
            
            logger.info(f"[ChatService] 推送测试用例到前端 | reply_id: {reply_id} | count: {count}")
            
        except json.JSONDecodeError as e:
            logger.warning(f"[ChatService] 无法解析测试用例 JSON: {e}")
        except Exception as e:
            logger.error(f"[ChatService] 提取测试用例失败: {e}")
    
    async def stop_agent_by_reply_id(self, reply_id: str) -> bool:
        """
        根据 reply_id 终止 Agent 进程
        
        Args:
            reply_id: 回复 ID
            
        Returns:
            bool: 是否成功终止
        """
        reply_data = self._pending_replies.get(reply_id)
        if not reply_data:
            logger.warning(f"[ChatService] 未找到回复记录: {reply_id}")
            return False
        
        conversation_id = reply_data.get("conversation_id")
        if not conversation_id:
            logger.warning(f"[ChatService] 回复记录中没有 conversation_id: {reply_id}")
            return False
        
        # ✅ 在终止前保存已累积的消息内容
        logger.info(f"[ChatService] 终止前保存消息 | reply_id: {reply_id}")
        for msg in reply_data.get("messages", []):
            accumulated_content = msg.get("_accumulated_content", "")
            if accumulated_content:
                message_id = msg.get("id", str(uuid.uuid4()))
                try:
                    self.database.create_message(
                        message_id=message_id,
                        conversation_id=conversation_id,
                        role="assistant",
                        content=accumulated_content
                    )
                    logger.info(
                        f"[ChatService] 终止时保存消息 | message_id: {message_id} | "
                        f"长度: {len(accumulated_content)}"
                    )
                except Exception as e:
                    # 如果消息已存在，跳过
                    if "已存在" in str(e) or "exists" in str(e).lower():
                        logger.warning(f"[ChatService] 消息已存在，跳过: {message_id}")
                    else:
                        logger.error(f"[ChatService] 保存消息失败: {e}")
        
        # 终止子进程
        success = self.process_manager.stop_agent(conversation_id)
        
        if success:
            # 标记为已完成（被用户终止）
            reply_data["finished"] = True
            reply_data["cancelled"] = True
            
            # 发送终止消息到消息队列
            await self.message_queue.put(reply_id, {
                "type": "cancelled",
                "message": "用户终止了请求"
            })
            
            # 结束 SSE 流
            await self.message_queue.put(reply_id, None)
            
            # 重置回复状态
            self.replying_state.set_replying(False)
            
            # 广播状态
            if self.socket_manager:
                await self.socket_manager.broadcast_replying_state(
                    self.replying_state.get_state()
                )
                await self.socket_manager.broadcast_cancelled(reply_id)
            
            logger.info(f"[ChatService] 成功终止 Agent | reply_id: {reply_id} | conversation_id: {conversation_id}")
            return True
        else:
            logger.warning(f"[ChatService] 终止 Agent 失败 | reply_id: {reply_id}")
            return False
    
    def cleanup(self):
        """清理资源"""
        self.process_manager.cleanup()
