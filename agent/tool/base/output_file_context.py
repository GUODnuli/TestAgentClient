# -*- coding: utf-8 -*-
"""
OutputFileContext — 全局单例，存储当前会话的输出目录上下文。

由 coordinator_main.py 在启动时通过 OutputFileContext.init() 初始化，
Skill 工具函数（output_manager）通过 get_output_context() 获取路径，
从而避免工厂闭包不可被静态发现的问题。
"""
import threading
from dataclasses import dataclass
from typing import Optional

_instance: Optional["OutputFileContext"] = None
_lock = threading.Lock()


@dataclass
class OutputFileContext:
    user_id: str
    conversation_id: str
    output_dir: str

    @staticmethod
    def init(user_id: str, conversation_id: str, output_dir: str) -> "OutputFileContext":
        """初始化（或覆盖）全局单例，每次会话启动时调用。"""
        global _instance
        with _lock:
            _instance = OutputFileContext(
                user_id=user_id,
                conversation_id=conversation_id,
                output_dir=output_dir,
            )
        return _instance

    @staticmethod
    def get() -> Optional["OutputFileContext"]:
        """获取当前单例，未初始化时返回 None。"""
        return _instance


def get_output_context() -> Optional[OutputFileContext]:
    """模块级便捷函数，供 Skill 工具函数直接调用。"""
    return _instance
