"""
日志系统模块

提供分级日志功能，支持按任务 ID 过滤。
日志级别从低到高：DEBUG < INFO < WARNING < ERROR < CRITICAL

重要提示：
- DEBUG 级别：详细的调试信息，通常在开发时使用
- INFO 级别：一般运行信息，生产环境推荐级别
- WARNING 级别：警告信息，不影响运行但需要注意
- ERROR 级别：错误信息，功能受影响但程序继续运行
- CRITICAL 级别：严重错误，可能导致程序崩溃

当日志级别设置为 INFO 时，DEBUG 级别的日志不会输出。
当日志级别设置为 DEBUG 时，所有级别的日志都会输出。
"""

import sys
import logging
from pathlib import Path
from typing import Optional
from loguru import logger
from datetime import datetime


class TaskContextFilter:
    """任务上下文过滤器 - 用于按任务 ID 过滤日志"""
    
    def __init__(self, task_id: Optional[str] = None):
        """
        初始化过滤器
        
        Args:
            task_id: 任务 ID，None 表示不过滤
        """
        self.task_id = task_id
    
    def __call__(self, record):
        """
        过滤记录
        
        Args:
            record: 日志记录
            
        Returns:
            是否保留该记录
        """
        if self.task_id is None:
            return True
        
        # 检查记录中是否包含 task_id 字段
        return record["extra"].get("task_id") == self.task_id


class Logger:
    """日志管理器"""
    
    def __init__(
        self,
        log_level: str = "INFO",
        log_file: Optional[str] = None,
        rotation: str = "10 MB",
        retention: str = "30 days",
        enable_console: bool = True,
        enable_file: bool = True,
    ):
        """
        初始化日志管理器
        
        Args:
            log_level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
            log_file: 日志文件路径
            rotation: 日志轮转规则（如 "10 MB", "1 day"）
            retention: 日志保留时间（如 "30 days"）
            enable_console: 是否启用控制台输出
            enable_file: 是否启用文件输出
        """
        self.log_level = log_level.upper()
        self.log_file = log_file
        self.rotation = rotation
        self.retention = retention
        self.enable_console = enable_console
        self.enable_file = enable_file
        
        # 移除默认的 handler
        logger.remove()
        
        # 添加控制台 handler
        if enable_console:
            logger.add(
                sys.stderr,
                level=self.log_level,
                format=(
                    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                    "<level>{level: <8}</level> | "
                    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                    "<level>{message}</level>"
                ),
                colorize=True,
            )
        
        # 添加文件 handler
        if enable_file and log_file:
            # 确保日志目录存在
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                log_file,
                level=self.log_level,
                format=(
                    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                    "{level: <8} | "
                    "{name}:{function}:{line} | "
                    "{message}"
                ),
                rotation=rotation,
                retention=retention,
                encoding="utf-8",
            )
        
        # 记录日志系统初始化
        logger.info(
            f"日志系统已初始化 | 级别: {self.log_level} | "
            f"提醒：日志级别从低到高为 DEBUG < INFO < WARNING < ERROR < CRITICAL"
        )
    
    def get_logger(self, task_id: Optional[str] = None):
        """
        获取日志记录器（带任务上下文）
        
        Args:
            task_id: 任务 ID
            
        Returns:
            日志记录器
        """
        if task_id:
            # 绑定任务 ID 到上下文
            return logger.bind(task_id=task_id)
        return logger
    
    def add_task_log_file(self, task_id: str, log_file: str):
        """
        为特定任务添加独立的日志文件
        
        Args:
            task_id: 任务 ID
            log_file: 任务日志文件路径
        """
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 添加任务专属的文件 handler
        logger.add(
            log_file,
            level=self.log_level,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            ),
            filter=TaskContextFilter(task_id),
            rotation=self.rotation,
            retention=self.retention,
            encoding="utf-8",
        )
        
        logger.info(f"为任务 {task_id} 创建独立日志文件: {log_file}")
    
    def set_level(self, level: str):
        """
        动态修改日志级别
        
        Args:
            level: 日志级别
        """
        self.log_level = level.upper()
        
        # 重新配置 logger
        logger.remove()
        self.__init__(
            log_level=self.log_level,
            log_file=self.log_file,
            rotation=self.rotation,
            retention=self.retention,
            enable_console=self.enable_console,
            enable_file=self.enable_file,
        )
        
        logger.info(f"日志级别已更新为: {self.log_level}")
    
    def debug(self, msg: str, **kwargs):
        """记录 DEBUG 级别日志"""
        logger.debug(msg, **kwargs)
    
    def info(self, msg: str, **kwargs):
        """记录 INFO 级别日志"""
        logger.info(msg, **kwargs)
    
    def warning(self, msg: str, **kwargs):
        """记录 WARNING 级别日志"""
        logger.warning(msg, **kwargs)
    
    def error(self, msg: str, **kwargs):
        """记录 ERROR 级别日志"""
        logger.error(msg, **kwargs)
    
    def critical(self, msg: str, **kwargs):
        """记录 CRITICAL 级别日志"""
        logger.critical(msg, **kwargs)
    
    def exception(self, msg: str, **kwargs):
        """记录异常信息（ERROR 级别，包含堆栈跟踪）"""
        logger.exception(msg, **kwargs)


# 全局日志管理器实例
_logger_instance: Optional[Logger] = None


def get_logger(
    task_id: Optional[str] = None,
    log_level: str = "INFO",
    log_file: Optional[str] = None,
) -> "logger":
    """
    获取全局日志记录器（单例模式）
    
    Args:
        task_id: 任务 ID（用于日志过滤）
        log_level: 日志级别
        log_file: 日志文件路径
        
    Returns:
        日志记录器
    """
    global _logger_instance
    
    if _logger_instance is None:
        _logger_instance = Logger(
            log_level=log_level,
            log_file=log_file or "./logs/app.log",
        )
    
    return _logger_instance.get_logger(task_id)


def init_logger(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    rotation: str = "10 MB",
    retention: str = "30 days",
    enable_console: bool = True,
    enable_file: bool = True,
) -> Logger:
    """
    初始化全局日志管理器
    
    Args:
        log_level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
        log_file: 日志文件路径
        rotation: 日志轮转规则
        retention: 日志保留时间
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
        
    Returns:
        日志管理器实例
    """
    global _logger_instance
    
    _logger_instance = Logger(
        log_level=log_level,
        log_file=log_file,
        rotation=rotation,
        retention=retention,
        enable_console=enable_console,
        enable_file=enable_file,
    )
    
    return _logger_instance


def debug(msg: str, task_id: Optional[str] = None, **kwargs):
    """
    记录 DEBUG 级别日志
    
    注意：只有当日志级别设置为 DEBUG 时，这些日志才会输出。
    
    Args:
        msg: 日志消息
        task_id: 任务 ID
        **kwargs: 额外参数
    """
    log = get_logger(task_id)
    log.debug(msg, **kwargs)


def info(msg: str, task_id: Optional[str] = None, **kwargs):
    """
    记录 INFO 级别日志
    
    Args:
        msg: 日志消息
        task_id: 任务 ID
        **kwargs: 额外参数
    """
    log = get_logger(task_id)
    log.info(msg, **kwargs)


def warning(msg: str, task_id: Optional[str] = None, **kwargs):
    """
    记录 WARNING 级别日志
    
    Args:
        msg: 日志消息
        task_id: 任务 ID
        **kwargs: 额外参数
    """
    log = get_logger(task_id)
    log.warning(msg, **kwargs)


def error(msg: str, task_id: Optional[str] = None, **kwargs):
    """
    记录 ERROR 级别日志
    
    Args:
        msg: 日志消息
        task_id: 任务 ID
        **kwargs: 额外参数
    """
    log = get_logger(task_id)
    log.error(msg, **kwargs)


def critical(msg: str, task_id: Optional[str] = None, **kwargs):
    """
    记录 CRITICAL 级别日志
    
    Args:
        msg: 日志消息
        task_id: 任务 ID
        **kwargs: 额外参数
    """
    log = get_logger(task_id)
    log.critical(msg, **kwargs)


def exception(msg: str, task_id: Optional[str] = None, **kwargs):
    """
    记录异常信息（ERROR 级别，包含堆栈跟踪）
    
    Args:
        msg: 日志消息
        task_id: 任务 ID
        **kwargs: 额外参数
    """
    log = get_logger(task_id)
    log.exception(msg, **kwargs)
