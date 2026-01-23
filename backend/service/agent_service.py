"""
Agent HTTP 服务

提供 RESTful API、Hook 端点和 Socket.IO 实时推送。
支持子进程模式：Agent 作为独立进程运行，通过 HTTP POST 回传消息。
"""

import asyncio
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Form, File, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import socketio

from backend.agent.chat_service import ChatService
from backend.common.storage import StorageManager
from backend.common.logger import Logger
from backend.common.database import Database
from backend.common.config import ModelConfig
from backend.auth import auth_router
from backend.auth.dependencies import get_current_user
from backend.auth.models import UserResponse
from backend.agent.conversation_routes import router as conversation_router


# 请求/响应模型
class ChatMessageRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class AgentMessageRequest(BaseModel):
    """Agent 消息推送请求"""
    replyId: str
    msg: Dict[str, Any]


class AgentFinishedRequest(BaseModel):
    """Agent 完成信号请求"""
    replyId: str


class SocketManager:
    """Socket.IO 管理器"""
    
    def __init__(self, sio: socketio.AsyncServer):
        self.sio = sio
        self._setup_handlers()
    
    def _setup_handlers(self):
        """设置 Socket.IO 事件处理器"""
        
        @self.sio.on("connect", namespace="/client")
        async def on_client_connect(sid, environ):
            print(f"[Socket] 客户端连接: {sid}")
        
        @self.sio.on("disconnect", namespace="/client")
        async def on_client_disconnect(sid):
            print(f"[Socket] 客户端断开: {sid}")
        
        @self.sio.on("joinChatRoom", namespace="/client")
        async def on_join_chat_room(sid, conversation_id):
            """加入聊天房间"""
            room = f"chat-{conversation_id}"
            await self.sio.enter_room(sid, room, namespace="/client")
            print(f"[Socket] {sid} 加入房间: {room}")
        
        @self.sio.on("leaveChatRoom", namespace="/client")
        async def on_leave_chat_room(sid, conversation_id):
            """离开聊天房间"""
            room = f"chat-{conversation_id}"
            await self.sio.leave_room(sid, room, namespace="/client")
            print(f"[Socket] {sid} 离开房间: {room}")
        
        # Agent 命名空间
        @self.sio.on("connect", namespace="/agent")
        async def on_agent_connect(sid, environ):
            print(f"[Socket] Agent 连接: {sid}")
        
        @self.sio.on("disconnect", namespace="/agent")
        async def on_agent_disconnect(sid):
            print(f"[Socket] Agent 断开: {sid}")
    
    async def broadcast_message(self, conversation_id: str, reply_id: str, message: Dict):
        """广播消息到聊天房间"""
        room = f"chat-{conversation_id}"
        await self.sio.emit(
            "pushReplies",
            {"replyId": reply_id, "message": message},
            room=room,
            namespace="/client"
        )
    
    async def broadcast_replying_state(self, state: Dict):
        """广播回复状态"""
        await self.sio.emit(
            "pushReplyingState",
            state,
            namespace="/client"
        )
    
    async def broadcast_finished(self, reply_id: str):
        """广播完成信号"""
        await self.sio.emit(
            "pushFinished",
            {"replyId": reply_id},
            namespace="/client"
        )
    
    async def send_interrupt(self):
        """发送中断信号到 Agent"""
        await self.sio.emit(
            "interrupt",
            {},
            namespace="/agent"
        )


class AgentService:
    """
    Agent HTTP 服务
    
    功能：
    - RESTful API（认证、对话历史）
    - Hook 端点（接收 Agent 消息回传）
    - Socket.IO 实时推送
    - 聊天对话服务（子进程模式）
    """
    
    def __init__(
        self,
        logger: Logger,
        database: Database,
        storage: StorageManager,
        config: Dict[str, Any],
        dify_config: Optional[Dict[str, Any]] = None,
        model_config: Optional[ModelConfig] = None
    ):
        self.logger = logger
        self.database = database
        self.storage = storage
        self.config = config
        self.model_config = model_config
        
        # 文件索引（内存缓存，开发阶段临时方案）
        # TODO: 长期方案应将文件元数据存入数据库，以支持服务重启和多实例部署
        self._chat_files_index: Dict[str, List[str]] = {}
        
        # 创建 FastAPI 应用
        self.app = FastAPI(
            title="MCP 智能体 API",
            description="智能化服务（子进程模式）",
            version="2.0.0"
        )
        
        # 配置 CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=config.get("cors_origins", ["*"]),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
        
        # 初始化 Socket.IO
        self.sio = socketio.AsyncServer(
            async_mode='asgi',
            cors_allowed_origins='*',
            logger=False,
            engineio_logger=False
        )
        self.socket_manager = SocketManager(self.sio)
        
        # 创建 ASGI 应用（Socket.IO + FastAPI）
        self.socket_app = socketio.ASGIApp(self.sio, self.app)
        
        # 初始化聊天服务（子进程模式）
        self.chat_service: Optional[ChatService] = None
        try:
            self.chat_service = ChatService(
                database=self.database,
                model_config=self.model_config,
                socket_manager=self.socket_manager
            )
            self.logger.info("ChatService 初始化成功（子进程模式）", component="AgentService")
        except Exception as e:
            self.logger.warning(
                f"ChatService 初始化失败，聊天功能不可用: {str(e)}",
                component="AgentService"
            )
        
        # 注册路由
        self._register_routes()
        
        # 注册 Hook 端点
        self._register_hook_routes()
        
        # 注册认证路由
        self.app.include_router(auth_router)
        
        # 注册对话历史路由
        self.app.include_router(conversation_router, prefix="/api")
        
        # 启动定时清理任务
        asyncio.create_task(self._periodic_cleanup())
        
        self.logger.info(
            "AgentService 初始化完成 | "
            f"CORS: {config.get('cors_origins', ['*'])} | "
            f"聊天服务: {'已启用' if self.chat_service else '未启用'} | "
            "Socket.IO: 已启用",
            component="AgentService"
        )
    
    def _register_routes(self):
        """注册 API 路由"""
        
        @self.app.get("/")
        async def root():
            """根路径"""
            return {
                "service": "MCP 智能体",
                "version": "1.0.0",
                "status": "running"
            }
        
        # ==================== 聊天相关路由 ====================
        
        @self.app.post("/api/chat/send", response_model=ChatResponse)
        async def send_chat_message(
            request: ChatMessageRequest,
            current_user: UserResponse = Depends(get_current_user)
        ):
            """发送聊天消息"""
            try:
                if not self.chat_service:
                    return ChatResponse(
                        success=False,
                        message="聊天服务未启用，请检查配置"
                    )
                
                self.logger.info(
                    f"[聊天] 收到消息 | user_id: {current_user.user_id} | conversation_id: {request.conversation_id} | 长度: {len(request.message)}",
                    conversation_id=request.conversation_id
                )
                
                result = await self.chat_service.send_message(
                    message=request.message,
                    user_id=current_user.user_id,
                    conversation_id=request.conversation_id
                )
                
                return ChatResponse(
                    success=True,
                    data=result
                )
            
            except Exception as e:
                self.logger.error(f"聊天消息处理失败: {str(e)}", exc_info=True)
                return ChatResponse(
                    success=False,
                    message=f"处理失败: {str(e)}"
                )
        
        @self.app.post("/api/chat/stream")
        async def send_chat_message_stream(
            request: ChatMessageRequest,
            current_user: UserResponse = Depends(get_current_user)
        ):
            """发送聊天消息（SSE 流式响应）"""
            if not self.chat_service:
                return ChatResponse(
                    success=False,
                    message="聊天服务未启用，请检查配置"
                )
            
            self.logger.info(
                f"[聊天SSE] 收到消息 | user_id: {current_user.user_id} | conversation_id: {request.conversation_id} | 长度: {len(request.message)}",
                conversation_id=request.conversation_id
            )
            
            async def generate_sse():
                """生成 SSE 事件流"""
                try:
                    # 获取已上传的文件列表
                    uploaded_files = self.get_uploaded_files(request.conversation_id) if request.conversation_id else []
                    
                    async for event in self.chat_service.send_message_streaming(
                        message=request.message,
                        user_id=current_user.user_id,
                        conversation_id=request.conversation_id,
                        uploaded_files=uploaded_files  # 传递文件列表
                    ):
                        event_type = event.get("type", "chunk")
                        data = json.dumps(event, ensure_ascii=False)
                        yield f"event: {event_type}\ndata: {data}\n\n"
                        # 小延迟确保前端能及时处理
                        await asyncio.sleep(0)
                except Exception as e:
                    self.logger.error(f"[聊天SSE] 流式生成失败: {str(e)}", exc_info=True)
                    error_data = json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False)
                    yield f"event: error\ndata: {error_data}\n\n"
            
            return StreamingResponse(
                generate_sse(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
        
        @self.app.post("/api/chat/upload")
        async def upload_chat_file(
            conversation_id: str = Form(...),
            file: UploadFile = File(...),
            current_user: UserResponse = Depends(get_current_user)
        ):
            """上传聊天文件"""
            try:
                content = await file.read()
                file_path = self.storage.save_chat_file(
                    user_id=current_user.user_id,
                    conversation_id=conversation_id,
                    filename=file.filename,
                    file_content=content
                )
                
                # 前端已重命名，直接使用传入的文件名
                if conversation_id not in self._chat_files_index:
                    self._chat_files_index[conversation_id] = []
                if file.filename not in self._chat_files_index[conversation_id]:
                    self._chat_files_index[conversation_id].append(file.filename)
                
                self.logger.info(
                    f"文件上传成功 | conversation_id: {conversation_id} | 文件: {file.filename}",
                    conversation_id=conversation_id
                )
                
                return {
                    "success": True,
                    "data": {
                        "filename": file.filename
                    }
                }
            except Exception as e:
                self.logger.error(f"文件上传失败: {str(e)}", exc_info=True)
                return {
                    "success": False,
                    "message": f"上传失败: {str(e)}"
                }
    
    def _register_hook_routes(self):
        """注册 Hook 端点（供 Agent 子进程调用）"""
        
        @self.app.post("/trpc/pushMessageToChatAgent")
        async def push_message_to_chat_agent(request: AgentMessageRequest):
            """
            接收 Agent 推送的消息
            
            由 Agent 子进程的 pre_print_hook 调用
            """
            try:
                self.logger.info(f"[Hook] 收到 Agent 消息 | reply_id: {request.replyId}")
                
                if self.chat_service:
                    await self.chat_service.handle_agent_message(
                        reply_id=request.replyId,
                        msg=request.msg
                    )
                
                return {"success": True}
            except Exception as e:
                self.logger.error(f"[Hook] 处理 Agent 消息失败: {str(e)}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        @self.app.post("/trpc/pushFinishedSignalToChatAgent")
        async def push_finished_signal_to_chat_agent(request: AgentFinishedRequest):
            """
            接收 Agent 完成信号
            
            由 Agent 子进程的 post_reply_hook 调用
            """
            try:
                self.logger.info(f"[Hook] 收到 Agent 完成信号 | reply_id: {request.replyId}")
                
                if self.chat_service:
                    await self.chat_service.handle_agent_finished(
                        reply_id=request.replyId
                    )
                
                return {"success": True}
            except Exception as e:
                self.logger.error(f"[Hook] 处理完成信号失败: {str(e)}", exc_info=True)
                return {"success": False, "error": str(e)}
        
        @self.app.post("/api/chat/interrupt")
        async def interrupt_agent(
            current_user: UserResponse = Depends(get_current_user)
        ):
            """中断 Agent 执行"""
            try:
                await self.socket_manager.send_interrupt()
                return {"success": True, "message": "中断信号已发送"}
            except Exception as e:
                self.logger.error(f"[中断] 发送中断信号失败: {str(e)}", exc_info=True)
                return {"success": False, "message": str(e)}
    
    def get_uploaded_files(self, conversation_id: str) -> List[str]:
        """
        获取指定会话的上传文件列表
        
        Args:
            conversation_id: 会话 ID
            
        Returns:
            文件名列表
        """
        return self._chat_files_index.get(conversation_id, [])

    async def _periodic_cleanup(self):
        """定期清理旧文件（每24小时运行一次）"""
        while True:
            try:
                self.logger.info("开始执行定期清理旧文件任务...")
                self.storage.cleanup_old_files(days_to_keep=7)
            except Exception as e:
                self.logger.error(f"定期清理任务失败: {str(e)}")
            
            # 等待 24 小时
            await asyncio.sleep(24 * 3600)
        
    def run(self, host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
        """
        运行服务
        
        Args:
            host: 服务主机地址
            port: 服务端口
            reload: 是否启用热重载（开发模式）
        """
        import uvicorn
        
        self.logger.info(
            f"启动 Agent HTTP 服务 | {host}:{port} | 热重载: {reload} | Socket.IO: 已启用",
            host=host,
            port=port,
            reload=reload
        )
        
        if reload:
            # 热重载模式：监控文件变化自动重启
            uvicorn.run(
                "backend.main:create_app",  # 使用app工厂函数
                factory=True,  # 告诉uvicorn这是一个app工厂函数
                host=host,
                port=port,
                reload=True,
                log_level="info",
                reload_dirs=["backend"],  # 监控backend目录
                reload_includes=["*.py"]  # 只监控Python文件
            )
        else:
            # 普通模式：使用 socket_app 以支持 Socket.IO
            uvicorn.run(self.socket_app, host=host, port=port, log_level="info")
