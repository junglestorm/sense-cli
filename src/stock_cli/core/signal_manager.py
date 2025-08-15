"""信号管理器"""

import signal
import sys
from typing import Optional, Any
from rich.console import Console

from ..core.app_state import app_state

console = Console()


class SignalManager:
    """信号管理器"""
    
    def __init__(self):
        pass
    
    def setup_signal_handlers(self):
        """设置信号处理器"""
        signal.signal(signal.SIGINT, self._signal_handler)  # Ctrl+C

    def _signal_handler(self, signum: int, frame: Any):
        """信号处理函数，用于处理 Ctrl+C"""
        if app_state.current_task and not app_state.current_task.done():
            console.print("\n[yellow]🛑 收到中断信号，正在停止当前任务...[/yellow]")
            app_state.interrupt_requested = True
            app_state.current_task.cancel()
        else:
            # 如果没有正在运行的任务，直接退出
            console.print("\n[red]Exiting...[/red]")
            sys.exit(0)