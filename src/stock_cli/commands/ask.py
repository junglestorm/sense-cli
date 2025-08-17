"""问答命令"""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.console import Console

from ..core.interaction import _interactive
from ..utils.signals import setup_signal_handlers

console = Console()


def ask(
    question: str,
    model: Optional[str] = typer.Option(None, "--model", "-m", help="覆盖默认模型"),
    config: Optional[str] = typer.Option(
        None, "--config", "-c", help="指定配置文件路径"
    ),
    output: str = typer.Option(
        "text", "--output", "-o", help="输出格式: text|json|yaml"
    ),
    debug: bool = typer.Option(False, "--debug", "-d", help="显示调试信息和推理过程"),
    no_color: bool = typer.Option(False, "--no-color", help="禁用彩色输出"),
    timeout: int = typer.Option(30, "--timeout", "-t", help="请求超时时间(秒)"),
    human_approval: bool = typer.Option(
        False, "--human-approval", help="启用人工审批模式"
    ),
    confirm: bool = typer.Option(False, "--confirm", "-y", help="最终答案需要人工确认"),
    session_id: str = typer.Option("default", "--session-id", "-s", help="指定会话ID（用于上下文持久化与连续记忆）"),
) -> None:
    """单轮问答模式 - 向AI提出问题并获得答案"""
    # 设置信号处理器
    setup_signal_handlers()


    

    # 处理输出格式
    if output not in ["text", "json", "yaml"]:
        console.print("[red]无效的输出格式，支持: text, json, yaml[/red]")
        raise typer.Exit(1)

    # 禁用颜色输出
    if no_color:
        console.color_system = None

    asyncio.run(
        _interactive(
            model,
            question,
            False,
            True,
            debug,
            human_approval,
            confirm,  # quiet=False, verbose=True
            output_format=output,
            timeout=timeout,
            session_id=session_id,
        )
    )