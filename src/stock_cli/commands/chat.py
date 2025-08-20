"""聊天命令"""

import asyncio
from typing import Optional, List

import typer
from rich.console import Console

from ..core.interaction import _interactive
from ..utils.signals import setup_signal_handlers

console = Console()


def chat(
    model: str = typer.Option("qwen2.5:7b", "--model", "-m", help="使用的模型名称"),
    minimal: bool = typer.Option(False, "--minimal", help="最小化输出"),
    session_id: str = typer.Option("default", "--session-id", "-s", help="指定会话ID（用于上下文持久化与连续记忆）"),
    trigger: Optional[List[str]] = typer.Option(None, "--trigger", "-t", help="指定要启用的触发器类型（可多次使用）"),
    role: Optional[str] = typer.Option(None, "--role", "-r", help="选择角色配置文件"),
) -> None:
    """进入交互式聊天模式（具有记忆功能）
    
    支持 /trigger 命令控制触发器：
    /trigger list - 查看可用触发器
    /trigger start [type] - 启动触发器
    /trigger stop [type] - 停止触发器
    /trigger config [type] [参数=值] - 配置触发器
    """
    
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
            triggers=trigger,
            role=role,
        )
    )