"""Stock Agent CLI 入口点"""

from __future__ import annotations

import typer

from .commands import ask, chat, tools, version
from .core.interaction import _interactive

app = typer.Typer(add_completion=False, help="Stock Agent CLI - AI驱动的股票分析工具")

# 注册命令
app.command()(version.version)
app.command()(ask.ask)
app.command()(chat.chat)
app.command()(tools.tools)

__version__ = "1.0.0"


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version_flag: bool = typer.Option(False, "--version", "-V", help="显示版本信息"),
):
    """Stock Agent CLI - AI驱动的股票分析工具"""
    from .utils.logging import setup_logging
    
    if version_flag:
        version.version()
        raise typer.Exit()

    from .utils.display import show_logo
    show_logo()

    if ctx.invoked_subcommand is None:
        # 默认进入对话模式
        

        setup_logging("ERROR")
        import asyncio
        asyncio.run(
            _interactive(None, None, False, True, False, False, False)
        )  # 默认启用 verbose


def main():
    """Entry point for stock-cli command."""
    app()


if __name__ == "__main__":  # pragma: no cover
    app()