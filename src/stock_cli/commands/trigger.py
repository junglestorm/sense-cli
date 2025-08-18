"""触发器命令"""

import asyncio
import signal
import sys
from typing import Optional

import typer
from rich.console import Console

from ..core.interaction import _run_agent_with_interrupt
from ..utils.signals import setup_signal_handlers

console = Console()

def trigger(
    trigger_type: str = typer.Option(..., "--type", "-t", help="触发器类型"),
) -> None:
    """启动指定类型的触发器"""
    
    # 设置信号处理器
    setup_signal_handlers()
    
    # 注册退出处理函数
    def signal_handler(sig, frame):
        console.print("\n[yellow]正在退出...[/yellow]")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 根据触发器类型启动相应的触发器
    if trigger_type == "ask_time":
        from ..triggers.ask_time import run_scheduler
        try:
            asyncio.run(run_scheduler())
        except KeyboardInterrupt:
            console.print("\n[green]已正常退出[/green]")
        except Exception as e:
            console.print(f"\n[red]执行出错: {e}[/red]")
            raise typer.Exit(1)
    else:
        console.print(f"[red]未知的触发器类型: {trigger_type}[/red]")
        raise typer.Exit(1)