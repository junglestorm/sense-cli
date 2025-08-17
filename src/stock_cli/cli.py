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
    debug: bool = typer.Option(False, "--debug", "-d", help="开启调试日志并输出到控制台"),
    log_console: bool = typer.Option(False, "--log-console", help="在控制台输出日志（不改变等级）"),
    session_id: str = typer.Option("default", "--session-id", "-s", help="指定会话ID（用于上下文持久化与连续记忆）"),
):
    """Stock Agent CLI - AI驱动的股票分析工具"""
    # 统一日志系统
    from .logs.logger import configure_logging
    # debug 时提升到 DEBUG 且打开控制台；否则仅当指定 --log-console 才向控制台输出
    configure_logging(level=("DEBUG" if debug else "ERROR"), console=(debug or log_console))

    if version_flag:
        version.version()
        raise typer.Exit()

    from .utils.display import show_logo
    show_logo()

    if ctx.invoked_subcommand is None:
        # 默认进入对话模式（使用回调级别的 session_id 与 debug）
        import asyncio
        asyncio.run(
            _interactive(
                model=None,
                once=None,
                quiet=False,
                verbose=True,
                debug=debug,
                human_approval=False,
                confirm=False,
                output_format="text",
                timeout=30,
                session_id=session_id,
            )
        )  # 默认启用 verbose


def main():
    """Entry point for stock-cli command."""
    app()


if __name__ == "__main__":  # pragma: no cover
    app()