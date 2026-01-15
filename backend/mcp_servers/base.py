"""
MCP Server 基类

提供 MCP Server 的通用功能和接口定义。
所有 MCP Server 应继承此基类。
"""

import sys
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from loguru import logger


class MCPError(Exception):
    """MCP 操作异常"""
    pass


class MCPServer(ABC):
    """MCP Server 抽象基类"""
    
    def __init__(self, server_id: str, version: str = "1.0.0"):
        """
        初始化 MCP Server
        
        Args:
            server_id: Server 唯一标识
            version: Server 版本号
        """
        self.server_id = server_id
        self.version = version
        self.logger = logger
        
        # 配置日志
        logger.remove()
        logger.add(
            sys.stderr,
            level="INFO",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
        )
        
        self.logger.info(f"MCP Server 启动 | ID: {server_id} | Version: {version}")
    
    @abstractmethod
    def get_tools(self) -> list[Dict[str, Any]]:
        """
        获取 Server 提供的工具列表
        
        Returns:
            工具定义列表，每个工具包含 name, description, input_schema
        """
        pass
    
    @abstractmethod
    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理工具调用
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            执行结果
            
        Raises:
            MCPError: 工具执行失败
        """
        pass
    
    def send_response(self, request_id: Any, result: Dict[str, Any]):
        """
        发送成功响应（JSON-RPC 2.0）
        
        Args:
            request_id: 请求 ID
            result: 执行结果
        """
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result
        }
        
        print(json.dumps(response), flush=True)
        self.logger.debug(f"响应已发送 | request_id: {request_id}")
    
    def send_error(self, request_id: Any, error_code: int, error_message: str):
        """
        发送错误响应（JSON-RPC 2.0）
        
        Args:
            request_id: 请求 ID
            error_code: 错误码
            error_message: 错误信息
        """
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": error_code,
                "message": error_message
            }
        }
        
        print(json.dumps(response), flush=True)
        self.logger.error(f"错误响应 | request_id: {request_id} | error: {error_message}")
    
    def process_request(self, request: Dict[str, Any]):
        """
        处理 JSON-RPC 请求
        
        Args:
            request: JSON-RPC 请求对象
        """
        request_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})
        
        try:
            # 处理工具列表请求
            if method == "tools/list":
                tools = self.get_tools()
                self.send_response(request_id, {"tools": tools})
                return
            
            # 处理工具调用请求
            if method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                
                if not tool_name:
                    self.send_error(request_id, -32602, "Missing tool name")
                    return
                
                result = self.handle_tool_call(tool_name, arguments)
                self.send_response(request_id, result)
                return
            
            # 未知方法
            self.send_error(request_id, -32601, f"Method not found: {method}")
        
        except MCPError as e:
            self.send_error(request_id, -32000, str(e))
        except Exception as e:
            self.logger.exception("处理请求时发生异常")
            self.send_error(request_id, -32603, f"Internal error: {str(e)}")
    
    def run(self):
        """
        运行 Server（从 stdin 读取请求并处理）
        """
        self.logger.info(f"MCP Server 运行中 | ID: {self.server_id}")
        
        try:
            for line in sys.stdin:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    request = json.loads(line)
                    self.process_request(request)
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON 解析失败: {e}")
                    self.send_error(None, -32700, "Parse error")
        
        except KeyboardInterrupt:
            self.logger.info("Server 停止（用户中断）")
        except Exception as e:
            self.logger.exception("Server 运行异常")
            sys.exit(1)
