"""信号处理工具"""

import asyncio
import signal
import sys
from typing import Optional


# 全局变量用于存储当前运行的任务
_current_task: Optional[asyncio.Task] = None
_interrupt_requested: bool = False


def _signal_handler(signum, frame):
    """信号处理函数，用于处理 Ctrl+C"""
    global _interrupt_requested, _current_task

    if _current_task and not _current_task.done():
        from rich.console import Console
        console = Console()
        console.print("\n[yellow]🛑 收到中断信号，正在停止当前任务...[/yellow]")
        _interrupt_requested = True
        _current_task.cancel()
    else:
        # 如果没有正在运行的任务，直接退出
        from rich.console import Console
        console = Console()
        console.print("\n[red]Exiting...[/red]")
        sys.exit(0)


def setup_signal_handlers():
    """设置信号处理器"""
    signal.signal(signal.SIGINT, _signal_handler)  # Ctrl+C