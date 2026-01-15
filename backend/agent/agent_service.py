"""
Agent HTTP 服务

提供 RESTful API 和 WebSocket 实时推送。
"""

import asyncio
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.agent.task_manager import TaskManager, TaskState
from backend.agent.workflow_orchestrator import WorkflowOrchestrator
from backend.common.logger import Logger
from backend.common.database import TaskType, TaskStatus


# 请求/响应模型
class CreateTaskRequest(BaseModel):
    task_type: str
    document_path: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    success: bool
    task_id: Optional[str] = None
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class AgentService:
    """
    Agent HTTP 服务
    
    功能：
    - RESTful API（任务管理、状态查询、报告下载）
    - WebSocket 实时推送（任务进度、日志）
    - 文件上传处理
    - CORS 支持
    """
    
    def __init__(
        self,
        task_manager: TaskManager,
        workflow_orchestrator: WorkflowOrchestrator,
        logger: Logger,
        config: Dict[str, Any]
    ):
        self.task_manager = task_manager
        self.workflow_orchestrator = workflow_orchestrator
        self.logger = logger
        self.config = config
        
        # 创建 FastAPI 应用
        self.app = FastAPI(
            title="MCP 接口测试智能体 API",
            description="接口测试自动化服务",
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
        
        # WebSocket 连接管理
        self.ws_connections: List[WebSocket] = []
        
        # 注册路由
        self._register_routes()
        
        self.logger.info(
            "AgentService 初始化完成 | "
            f"CORS: {config.get('cors_origins', ['*'])}",
            component="AgentService"
        )
    
    def _register_routes(self):
        """注册 API 路由"""
        
        @self.app.get("/")
        async def root():
            """根路径"""
            return {
                "service": "MCP 接口测试智能体",
                "version": "1.0.0",
                "status": "running"
            }
        
        @self.app.post("/api/tasks", response_model=TaskResponse)
        async def create_task(request: CreateTaskRequest):
            """创建新任务"""
            try:
                task_type = TaskType(request.task_type)
                task_id = self.task_manager.create_task(
                    task_type=task_type,
                    document_path=request.document_path
                )
                
                # 异步执行工作流
                if request.document_path:
                    asyncio.create_task(
                        self._execute_workflow_async(
                            task_id,
                            request.document_path,
                            request.config
                        )
                    )
                
                return TaskResponse(
                    success=True,
                    task_id=task_id,
                    message="任务已创建"
                )
            
            except Exception as e:
                self.logger.error(f"创建任务失败: {str(e)}", exc_info=True)
                return TaskResponse(
                    success=False,
                    message=f"创建任务失败: {str(e)}"
                )
        
        @self.app.get("/api/tasks/{task_id}", response_model=TaskResponse)
        async def get_task(task_id: str):
            """获取任务信息"""
            try:
                task_info = self.task_manager.get_task_info(task_id)
                
                if not task_info:
                    raise HTTPException(status_code=404, detail="任务不存在")
                
                return TaskResponse(
                    success=True,
                    data=task_info
                )
            
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"获取任务失败: {str(e)}", exc_info=True)
                return TaskResponse(
                    success=False,
                    message=f"获取任务失败: {str(e)}"
                )
        
        @self.app.get("/api/tasks", response_model=TaskResponse)
        async def list_tasks(
            status: Optional[str] = None,
            task_type: Optional[str] = None,
            limit: int = 100
        ):
            """列出任务"""
            try:
                status_filter = TaskStatus(status) if status else None
                type_filter = TaskType(task_type) if task_type else None
                
                tasks = self.task_manager.list_tasks(
                    status=status_filter,
                    task_type=type_filter,
                    limit=limit
                )
                
                return TaskResponse(
                    success=True,
                    data={"tasks": tasks}
                )
            
            except Exception as e:
                self.logger.error(f"列出任务失败: {str(e)}", exc_info=True)
                return TaskResponse(
                    success=False,
                    message=f"列出任务失败: {str(e)}"
                )
        
        @self.app.post("/api/tasks/{task_id}/retry", response_model=TaskResponse)
        async def retry_task(task_id: str):
            """重试失败的任务"""
            try:
                success = self.task_manager.retry_task(task_id)
                
                if success:
                    # 重新执行工作流
                    task_info = self.task_manager.get_task_info(task_id)
                    document_path = task_info.get("document_path")
                    
                    if document_path:
                        asyncio.create_task(
                            self._execute_workflow_async(task_id, document_path, {})
                        )
                    
                    return TaskResponse(
                        success=True,
                        message="任务重试已启动"
                    )
                else:
                    return TaskResponse(
                        success=False,
                        message="任务重试失败"
                    )
            
            except Exception as e:
                self.logger.error(f"重试任务失败: {str(e)}", exc_info=True)
                return TaskResponse(
                    success=False,
                    message=f"重试任务失败: {str(e)}"
                )
        
        @self.app.post("/api/tasks/{task_id}/cancel", response_model=TaskResponse)
        async def cancel_task(task_id: str, reason: Optional[str] = None):
            """取消任务"""
            try:
                success = self.task_manager.cancel_task(task_id, reason)
                
                return TaskResponse(
                    success=success,
                    message="任务已取消" if success else "取消任务失败"
                )
            
            except Exception as e:
                self.logger.error(f"取消任务失败: {str(e)}", exc_info=True)
                return TaskResponse(
                    success=False,
                    message=f"取消任务失败: {str(e)}"
                )
        
        @self.app.get("/api/statistics", response_model=TaskResponse)
        async def get_statistics():
            """获取统计信息"""
            try:
                stats = self.task_manager.get_task_statistics()
                
                return TaskResponse(
                    success=True,
                    data=stats
                )
            
            except Exception as e:
                self.logger.error(f"获取统计失败: {str(e)}", exc_info=True)
                return TaskResponse(
                    success=False,
                    message=f"获取统计失败: {str(e)}"
                )
        
        @self.app.post("/api/upload", response_model=TaskResponse)
        async def upload_file(file: UploadFile = File(...)):
            """上传文档文件"""
            try:
                # 验证文件类型
                allowed_extensions = [".json", ".yaml", ".yml", ".doc", ".docx"]
                file_ext = Path(file.filename).suffix.lower()
                
                if file_ext not in allowed_extensions:
                    return TaskResponse(
                        success=False,
                        message=f"不支持的文件格式: {file_ext}。支持的格式: {', '.join(allowed_extensions)}"
                    )
                
                # 保存文件
                upload_dir = Path(self.config.get("upload_dir", "data/uploads"))
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                file_path = upload_dir / file.filename
                
                # 读取并写入文件
                content = await file.read()
                with open(file_path, "wb") as f:
                    f.write(content)
                
                # 计算文件大小
                file_size_kb = round(len(content) / 1024, 2)
                
                # 根据用户偏好添加详细日志
                file_type = "Word文档" if file_ext in [".doc", ".docx"] else "API文档"
                self.logger.info(
                    f"{file_type}上传成功 | 文件: {file.filename} | 大小: {file_size_kb}KB | 路径: {file_path}",
                    file=str(file_path),
                    size_kb=file_size_kb,
                    file_type=file_type
                )
                
                return TaskResponse(
                    success=True,
                    message=f"{file_type}上传成功",
                    data={
                        "file_path": str(file_path),
                        "file_name": file.filename,
                        "file_size_kb": file_size_kb,
                        "file_type": file_ext
                    }
                )
            
            except Exception as e:
                self.logger.error(f"文件上传失败: {str(e)}", exc_info=True)
                return TaskResponse(
                    success=False,
                    message=f"文件上传失败: {str(e)}"
                )
        
        @self.app.get("/api/reports/{task_id}")
        async def download_report(task_id: str, format: str = "html"):
            """下载测试报告"""
            try:
                # 获取报告路径
                report_dir = Path(self.config.get("storage_root", "data")) / task_id
                
                if format == "html":
                    report_file = report_dir / "report.html"
                elif format == "markdown":
                    report_file = report_dir / "report.md"
                else:
                    raise HTTPException(status_code=400, detail="不支持的格式")
                
                if not report_file.exists():
                    raise HTTPException(status_code=404, detail="报告不存在")
                
                return FileResponse(
                    path=report_file,
                    filename=f"test_report_{task_id}.{format}",
                    media_type="text/html" if format == "html" else "text/markdown"
                )
            
            except HTTPException:
                raise
            except Exception as e:
                self.logger.error(f"下载报告失败: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket 连接（用于实时推送）"""
            await websocket.accept()
            self.ws_connections.append(websocket)
            
            self.logger.info("WebSocket 连接已建立", ws_count=len(self.ws_connections))
            
            try:
                while True:
                    # 保持连接
                    data = await websocket.receive_text()
                    # 可以处理客户端发送的消息
                    
            except WebSocketDisconnect:
                self.ws_connections.remove(websocket)
                self.logger.info("WebSocket 连接已断开", ws_count=len(self.ws_connections))
    
    async def _execute_workflow_async(
        self,
        task_id: str,
        document_path: str,
        config: Optional[Dict[str, Any]]
    ):
        """异步执行工作流"""
        try:
            success = await self.workflow_orchestrator.execute_workflow(
                task_id,
                document_path,
                config
            )
            
            # 推送完成消息
            await self._broadcast_ws_message({
                "type": "task_completed",
                "task_id": task_id,
                "success": success
            })
        
        except Exception as e:
            self.logger.error(
                f"工作流执行失败 | task_id: {task_id} | 错误: {str(e)}",
                task_id=task_id,
                error=str(e),
                exc_info=True
            )
            
            # 推送错误消息
            await self._broadcast_ws_message({
                "type": "task_error",
                "task_id": task_id,
                "error": str(e)
            })
    
    async def _broadcast_ws_message(self, message: Dict[str, Any]):
        """广播 WebSocket 消息"""
        if not self.ws_connections:
            return
        
        import json
        message_json = json.dumps(message)
        
        for ws in self.ws_connections[:]:  # 复制列表避免迭代时修改
            try:
                await ws.send_text(message_json)
            except Exception as e:
                self.logger.warning(f"WebSocket 发送失败: {str(e)}")
                self.ws_connections.remove(ws)
    
    def run(self, host: str = "0.0.0.0", port: int = 8000):
        """运行服务"""
        import uvicorn
        
        self.logger.info(
            f"启动 Agent HTTP 服务 | {host}:{port}",
            host=host,
            port=port
        )
        
        uvicorn.run(self.app, host=host, port=port, log_level="info")
