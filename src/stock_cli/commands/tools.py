"""工具命令"""

import asyncio

import typer
from rich.console import Console

from ..utils.logging import setup_logging

console = Console()


def tools() -> None:
    """列出可用工具"""
    from ..core.interaction import _show_tools
    setup_logging("ERROR")
    asyncio.run(_show_tools())