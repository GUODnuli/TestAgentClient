# -*- coding: utf-8 -*-
"""通用工具函数"""
import platform
import os
from pathlib import Path

from .constants import NAME_APP


def get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent.parent.parent


def get_local_file_path(filename: str) -> str:
    """
    获取本地文件路径（跨平台支持）
    
    Args:
        filename: 文件名
        
    Returns:
        完整文件路径
    """
    if platform.system() == "Windows":
        local_path = os.path.join(os.getenv("APPDATA", ""), NAME_APP)
    elif platform.system() == "Darwin":
        local_path = os.path.join(
            os.getenv("HOME", ""), "Library", "Application Support", NAME_APP
        )
    elif platform.system() == "Linux":
        local_path = os.path.join(os.getenv("HOME", ""), ".local", "share", NAME_APP)
    else:
        # 回退到项目 storage 目录
        local_path = str(get_project_root() / "storage" / NAME_APP)

    if not os.path.exists(local_path):
        os.makedirs(local_path, exist_ok=True)

    return os.path.join(local_path, filename)


def get_storage_path(subdir: str = "") -> Path:
    """
    获取存储目录路径
    
    Args:
        subdir: 子目录名
        
    Returns:
        存储目录路径
    """
    storage_root = get_project_root() / "storage"
    if subdir:
        path = storage_root / subdir
    else:
        path = storage_root
    
    path.mkdir(parents=True, exist_ok=True)
    return path
