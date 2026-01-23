"""
Agent 核心模块

提供聊天服务、Agent 子进程管理等核心功能。
采用子进程模式：Agent 作为独立进程运行，通过 HTTP Hook 回传消息。
"""

from .chat_service import ChatService, ReplyingStateManager, AgentProcessManager

__all__ = [
    "ChatService",
    "ReplyingStateManager",
    "AgentProcessManager",
]
