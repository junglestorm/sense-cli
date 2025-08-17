"""日志工具"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List


def setup_logging(level: str = "INFO"):
    """设置日志配置，只输出到文件，不输出到控制台"""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # 完全清除现有的日志处理器
    def setup_logging_inner(log_path: str, level=logging.ERROR, max_bytes=5*1024*1024, backup_count=5):
        handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.handlers.clear()
        root_logger.addHandler(handler)

    # 初始化主日志
    setup_logging_inner("logs/app.log")

    # 禁用所有可能产生控制台输出的日志
    noisy_loggers = [
        "posthog",
        "httpx",
        "httpcore",
        "openai",
        "mcp",
        "anyio",
        "asyncio",
        "src.tools.mcp_server_manager",
        "mcp.server.lowlevel.server",
        "__main__",
        "src.tools.mcp_server.stock_core_server",
        "src.tools.mcp_server.stock_news_server",
        "src.tools.mcp_server.time_server",
    ]

    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)  # 只允许严重错误
        logger.propagate = False
        # 移除所有处理器
        logger.handlers.clear()