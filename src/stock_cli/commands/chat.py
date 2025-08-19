"""聊天命令"""

import asyncio
from typing import Optional

import typer
from rich.console import Console

from ..core.interaction import _interactive
from ..utils.signals import setup_signal_handlers

console = Console()


def chat(
    model: str = typer.Option("qwen2.5:7b", "--model", "-m", help="使用的模型名称"),
    minimal: bool = typer.Option(False, "--minimal", help="最小化输出"),
    session_id: str = typer.Option("default", "--session-id", "-s", help="指定会话ID（用于上下文持久化与连续记忆）"),
    triggers_path: Optional[str] = typer.Option(None, "--trigger", help="触发器配置路径（可选，用于兼容测试参数）"),
) -> None:
    """进入交互式聊天模式（具有记忆功能）"""
    
    # 设置信号处理器
    setup_signal_handlers()

    

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
            session_id=session_id,
            triggers_path=triggers_path,
        )
    )