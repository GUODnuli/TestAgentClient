# -*- coding: utf-8 -*-
"""
Agent 侧 Socket.IO 连接

用于接收来自 Server 的中断信号
"""
import socketio
from agentscope.agent import ReActAgent

from .constants import NAMESPACE_AGENT, EVENT_INTERRUPT


class StudioConnect:
    """Agent 与 Server 的 Socket 连接"""

    def __init__(self, url: str, agent: ReActAgent, post_reply_hook: callable):
        """
        初始化连接
        
        Args:
            url: Server URL
            agent: ReActAgent 实例
            post_reply_hook: 回复完成后的 Hook 函数
        """
        self.url = url
        self.agent = agent
        self.post_reply_hook = post_reply_hook
        
        self.sio = socketio.AsyncClient(
            reconnection=True,
            reconnection_attempts=5,
            reconnection_delay=1,
            reconnection_delay_max=3,
        )

        @self.sio.on("connect", namespace=NAMESPACE_AGENT)
        async def on_connect():
            print(f"[Socket] 已连接到 Server: {self.url}")

        @self.sio.on("disconnect", namespace=NAMESPACE_AGENT)
        async def on_disconnect():
            print(f"[Socket] 已断开连接: {self.url}")

        @self.sio.on(EVENT_INTERRUPT, namespace=NAMESPACE_AGENT)
        async def on_interrupt():
            print("[Socket] 收到中断信号，正在停止 Agent...")
            await self.agent.interrupt()
            # 通知 Server 回复已完成
            self.post_reply_hook(self.agent)

    async def connect(self) -> None:
        """建立连接"""
        try:
            await self.sio.connect(
                self.url,
                namespaces=[NAMESPACE_AGENT],
            )
        except Exception as e:
            raise RuntimeError(
                f"无法连接到 Server ({self.url})，请检查服务是否运行。"
            ) from e

    async def disconnect(self) -> None:
        """断开连接"""
        try:
            print("[Socket] 正在断开连接...")
            await self.sio.disconnect()
            print("[Socket] 已成功断开。")
        except Exception as e:
            print(f"[Socket] 断开连接失败: {e}")
