"""
MCP 客户端

实现 StdIO 传输和 JSON-RPC 2.0 协议通信。
"""

import json
import asyncio
import uuid
from typing import Any, Dict, List, Optional
from subprocess import Popen, PIPE

from backend.common.logger import Logger


class MCPClient:
    """
    MCP 客户端
    
    功能：
    - StdIO 传输（通过子进程通信）
    - JSON-RPC 2.0 协议实现
    - 工具列表发现
    - 工具调用
    - 异步通信支持
    """
    
    def __init__(self, server_command: List[str], logger: Logger):
        """
        初始化 MCP 客户端
        
        Args:
            server_command: Server 启动命令（如 ["python", "server.py"]）
            logger: 日志记录器
        """
        self.server_command = server_command
        self.logger = logger
        self.process: Optional[Popen] = None
        self.request_id_counter = 0
        
    async def connect(self) -> bool:
        """
        连接到 MCP Server
        
        Returns:
            连接是否成功
        """
        try:
            self.process = Popen(
                self.server_command,
                stdin=PIPE,
                stdout=PIPE,
                stderr=PIPE,
                text=True,
                bufsize=1
            )
            
            self.logger.info(
                f"MCP 客户端已连接 | 命令: {' '.join(self.server_command)}",
                command=self.server_command
            )
            
            # 发送初始化请求
            init_response = await self.send_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {}
            })
            
            if init_response.get("result"):
                self.logger.info("MCP Server 初始化成功", response=init_response)
                return True
            
            return False
        
        except Exception as e:
            self.logger.error(
                f"MCP 客户端连接失败: {str(e)}",
                error=str(e),
                exc_info=True
            )
            return False
    
    async def disconnect(self):
        """断开连接"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None
            self.logger.info("MCP 客户端已断开")
    
    async def send_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发送 JSON-RPC 请求
        
        Args:
            method: 方法名
            params: 参数
            
        Returns:
            响应数据
        """
        if not self.process:
            raise RuntimeError("MCP 客户端未连接")
        
        request_id = self._generate_request_id()
        
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params or {}
        }
        
        self.logger.debug(
            f"发送 MCP 请求 | 方法: {method} | ID: {request_id}",
            method=method,
            request_id=request_id
        )
        
        # 发送请求
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json)
        self.process.stdin.flush()
        
        # 接收响应
        response_line = self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("MCP Server 未响应")
        
        response = json.loads(response_line)
        
        self.logger.debug(
            f"收到 MCP 响应 | ID: {request_id}",
            request_id=request_id,
            response=response
        )
        
        # 检查错误
        if "error" in response:
            error = response["error"]
            raise RuntimeError(
                f"MCP 错误: {error.get('message', 'Unknown error')}"
            )
        
        return response
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        列出 Server 支持的工具
        
        Returns:
            工具列表
        """
        response = await self.send_request("tools/list")
        tools = response.get("result", {}).get("tools", [])
        
        self.logger.info(
            f"获取到 {len(tools)} 个工具",
            tool_count=len(tools)
        )
        
        return tools
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        response = await self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        result = response.get("result", {})
        
        self.logger.info(
            f"工具调用完成 | 工具: {tool_name}",
            tool=tool_name
        )
        
        return result
    
    def _generate_request_id(self) -> str:
        """生成请求 ID"""
        self.request_id_counter += 1
        return f"req_{self.request_id_counter}"


class MCPClientManager:
    """
    MCP 客户端管理器
    
    管理多个 MCP Server 客户端连接。
    """
    
    def __init__(self, logger: Logger):
        self.logger = logger
        self.clients: Dict[str, MCPClient] = {}
    
    async def register_server(
        self,
        name: str,
        command: List[str]
    ) -> bool:
        """
        注册并连接 MCP Server
        
        Args:
            name: Server 名称
            command: 启动命令
            
        Returns:
            注册是否成功
        """
        client = MCPClient(command, self.logger)
        success = await client.connect()
        
        if success:
            self.clients[name] = client
            self.logger.info(f"MCP Server 已注册: {name}", server=name)
            return True
        
        return False
    
    async def disconnect_all(self):
        """断开所有客户端"""
        for name, client in self.clients.items():
            await client.disconnect()
            self.logger.info(f"MCP Server 已断开: {name}", server=name)
        
        self.clients.clear()
    
    def get_client(self, name: str) -> Optional[MCPClient]:
        """获取客户端"""
        return self.clients.get(name)
