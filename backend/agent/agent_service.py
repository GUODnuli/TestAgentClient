"""
Agent HTTP 服务

提供 RESTful API 和 WebSocket 实时推送。
"""

import asyncio
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agent.task_manager import TaskManager
from backend.agent.workflow_orchestrator import WorkflowOrchestrator
from backend.agent.chat_agent import ChatService
from backend.common.logger import Logger
from backend.common.database import Database
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


class AgentService:
    """
    Agent HTTP 服务
    
    功能：
    - RESTful API（认证、对话历史）
    - CORS 支持
    - 聊天对话服务
    """
    
    def __init__(
        self,
        task_manager: TaskManager,
        workflow_orchestrator: WorkflowOrchestrator,
        logger: Logger,
        database: Database,
        config: Dict[str, Any],
        dify_config: Optional[Dict[str, Any]] = None
    ):
        self.task_manager = task_manager
        self.workflow_orchestrator = workflow_orchestrator
        self.logger = logger
        self.database = database
        self.config = config
        
        # 创建 FastAPI 应用
        self.app = FastAPI(
            title="MCP 智能体 API",
            description="智能化服务",
            version="1.0.0"
        )
        
        # 配置 CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=config.get("cors_origins", ["*"]),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
        
        # 初始化聊天服务
        self.chat_service: Optional[ChatService] = None
        if dify_config:
            try:
                self.chat_service = ChatService(dify_config, self.database)
                self.logger.info("ChatService 初始化成功", component="AgentService")
            except Exception as e:
                self.logger.warning(
                    f"ChatService 初始化失败，聊天功能不可用: {str(e)}",
                    component="AgentService"
                )
        
        # 注册路由
        self._register_routes()
        
        # 注册认证路由
        self.app.include_router(auth_router)
        
        # 注册对话历史路由
        self.app.include_router(conversation_router, prefix="/api")
        
        self.logger.info(
            "AgentService 初始化完成 | "
            f"CORS: {config.get('cors_origins', ['*'])} | "
            f"聊天服务: {'已启用' if self.chat_service else '未启用'}",
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
                        message="聊天服务未启用，请检查 Dify 配置"
                    )
                
                self.logger.info(
                    f"[聊天] 收到消息 | user_id: {current_user.user_id} | conversation_id: {request.conversation_id} | 长度: {len(request.message)}",
                    conversation_id=request.conversation_id
                )
                
                result = self.chat_service.send_message(
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
                    message="聊天服务未启用，请检查 Dify 配置"
                )
            
            self.logger.info(
                f"[聊天SSE] 收到消息 | user_id: {current_user.user_id} | conversation_id: {request.conversation_id} | 长度: {len(request.message)}",
                conversation_id=request.conversation_id
            )
            
            async def generate_sse():
                """生成 SSE 事件流"""
                try:
                    for event in self.chat_service.send_message_streaming(
                        message=request.message,
                        user_id=current_user.user_id,
                        conversation_id=request.conversation_id
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
            f"启动 Agent HTTP 服务 | {host}:{port} | 热重载: {reload}",
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
            # 普通模式
            uvicorn.run(self.app, host=host, port=port, log_level="info")
