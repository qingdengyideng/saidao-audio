"""统一的日志配置模块，支持通过环境变量控制日志级别"""
from __future__ import annotations

import logging
import os
import sys


def setup_logging(level: str | None = None) -> None:
    """
    配置应用日志系统，输出到 stdout 以便 docker logs 捕获
    
    Args:
        level: 日志级别，默认从环境变量 LOG_LEVEL 读取，未设置则为 INFO
    """
    log_level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    
    # 将日志级别字符串转换为 logging 常量
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # 配置根 logger
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,  # 输出到 stdout，确保 docker logs 可见
        force=True,  # 强制重新配置（覆盖已有配置）
    )
    
    # 为第三方库设置更高的日志级别，减少噪音
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # 记录日志系统启动信息
    logger = logging.getLogger(__name__)
    logger.info(f"日志系统已初始化，级别={log_level}")


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的 logger
    
    Args:
        name: logger 名称，通常使用 __name__
        
    Returns:
        配置好的 Logger 实例
    """
    return logging.getLogger(name)
