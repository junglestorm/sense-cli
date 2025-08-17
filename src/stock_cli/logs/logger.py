"""统一日志配置模块

- 仅默认写入文件（logs/app.log），不向控制台输出，避免污染终端
- 提供可选控制台输出（用于 --debug 等场景）
- 统一第三方 noisy logger 的等级和传播
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


NOISY_LOGGERS = [
    # 常见三方/底层模块
    "posthog",
    "httpx",
    "httpcore",
    "openai",
    "anyio",
    "asyncio",
    "urllib3",
    "mcp",
    "mcp.server",
    "mcp.client",
    "mcp.server.fastmcp",
    "mcp.server.lowlevel",
    # 本项目中可能产生过多输出的路径（按需补充/收缩）
    "src.tools.mcp_server_manager",
    "mcp.server.lowlevel.server",
    "src.tools.mcp_server.stock_core_server",
    "src.tools.mcp_server.stock_news_server",
    "src.tools.mcp_server.time_server",
]


def configure_logging(level: str = "INFO", console: bool = False, log_path: Optional[str] = None) -> None:
    """配置全局日志系统
    - level: 字符串等级，INFO/ERROR/DEBUG 等
    - console: 是否在控制台输出日志（默认 False，保持终端整洁）
    - log_path: 日志文件路径，默认 logs/app.log
    """
    # 准备日志目录
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_path = Path(log_path or (log_dir / "app.log"))

    # 清理 root logger 现有 handler
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # 级别
    try:
        numeric_level = getattr(logging, level.upper())
    except Exception:
        numeric_level = logging.INFO

    # 文件 handler
    file_handler = RotatingFileHandler(str(file_path), maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root_logger.addHandler(file_handler)

    # 可选：控制台 handler（调试时使用）
    if console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root_logger.addHandler(console_handler)

    # 设置 root 级别
    root_logger.setLevel(numeric_level)

    # 收敛 noisy logger
    for name in NOISY_LOGGERS:
        lg = logging.getLogger(name)
        # 对第三方模块采用较高阈值，避免刷屏
        lg.setLevel(max(numeric_level, logging.WARNING))
        lg.propagate = False
        # 清空它们自己的 handler，确保只走我们统一的 root handlers
        lg.handlers.clear()


def get_logger(name: str) -> logging.Logger:
    """获取模块 logger（便于后续扩展统一模式）"""
    return logging.getLogger(name)