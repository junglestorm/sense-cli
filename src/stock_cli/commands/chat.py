"""聊天命令"""

import asyncio
from typing import Optional

import typer
from rich.console import Console

from ..core.interaction import _interactive
from ..logs.logger import configure_logging
from ..utils.signals import setup_signal_handlers

console = Console()


def chat(
    model: str = typer.Option("qwen2.5:7b", "--model", "-m", help="使用的模型名称"),
    minimal: bool = typer.Option(False, "--minimal", help="最小化输出"),
) -> None:
    """进入交互式聊天模式（具有记忆功能）"""
    
    # 设置信号处理器
    setup_signal_handlers()
    # 统一日志配置：仅写入文件，避免污染终端
    configure_logging(level="ERROR", console=False)

    

    asyncio.run(
        _interactive(
            model=model,
            once=None,
            quiet=minimal,  # minimal模式对应quiet
            verbose=not minimal,  # 非minimal时verbose
            debug=False,
            human_approval=False,
            confirm=False,
            output_format="text",
            timeout=30,
        )
    )