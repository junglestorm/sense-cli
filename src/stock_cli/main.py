"""Stock Agent CLI (MVP)

特性 (聚焦 Agent 能力 / 类 Gemini CLI 体验):
    - ask: 单轮问答, 支持 --model 覆盖, --json 结构化输出, --show-thought 显示推理阶段
    - chat: 多轮对话 (首轮流式输出)

JSON 输出结构: {"answer","model","latency","reasoning"}
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional
from pathlib import Path

import typer
from rich import print
from rich.panel import Panel
from rich.console import Console

from .agent.runtime import (
    ensure_kernel,
    cleanup_kernel,
    current_model,
    get_kernel,
)
from .tools.mcp_server_manager import MCPServerManager
from .core.app_state import app_state

# 导入新创建的模块
from .core.signal_manager import SignalManager
from .core.cli_handler import CLICommandHandler
from .core.cli_session import CLISessionManager
from .agent.task_executor import TaskExecutor

app = typer.Typer(add_completion=False, help="Stock Agent CLI - AI驱动的股票分析工具")
console = Console()

__version__ = "1.0.0"

# 初始化组件
signal_manager = SignalManager()
cli_handler = CLICommandHandler()
cli_session = CLISessionManager()


@app.command()
def version():
    """显示版本信息"""
    console.print(f"Stock Agent CLI v{__version__}")
    console.print("AI-Powered Stock Analysis Tool powered by ReAct Architecture")


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="显示版本信息"),
):
    """Stock Agent CLI - AI驱动的股票分析工具"""
    if version:
        console.print(f"Stock Agent CLI v{__version__}")
        console.print("AI-Powered Stock Analysis Tool powered by ReAct Architecture")
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        # 默认进入对话模式
        if not _check_llm_config():
            console.print("[red]LLM配置不完整，请配置 config/settings.yaml[/red]")
            raise typer.Exit(1)

        _setup_logging("ERROR")
        asyncio.run(
            _interactive(None, None, False, True, False, False, False)
        )  # 默认启用 verbose


def _setup_logging(level: str = "INFO"):
    """设置日志配置，只输出到文件，不输出到控制台"""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # 完全清除现有的日志处理器
    from logging.handlers import RotatingFileHandler

    def setup_logging(log_path: str, level=logging.ERROR, max_bytes=5*1024*1024, backup_count=5):
        handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        root_logger.handlers.clear()
        root_logger.addHandler(handler)

    # 初始化主日志
    setup_logging("logs/app.log")

    # 禁用所有可能产生控制台输出的日志
    noisy_loggers = [
        "posthog",
        "httpx",
        "httpcore",
        "openai",
        "mcp",
        "anyio",
        "asyncio",
        "src.tools.mcp_server_manager",
        "mcp.server.lowlevel.server",
        "__main__",
        "src.tools.mcp_server.stock_core_server",
        "src.tools.mcp_server.stock_news_server",
        "src.tools.mcp_server.time_server",
    ]

    for logger_name in noisy_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL)  # 只允许严重错误
        logger.propagate = False
        # 移除所有处理器
        logger.handlers.clear()


def _check_llm_config() -> bool:
    """检查LLM配置是否完整"""
    project_root = Path(__file__).resolve().parent.parent.parent
    settings_path = project_root / "config" / "settings.yaml"

    print(f"DEBUG: 配置文件路径: {settings_path}")
    print(f"DEBUG: 文件是否存在: {settings_path.exists()}")

    if not settings_path.exists():
        return False

    try:
        import yaml
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}

        llm_config = settings.get("llm", {})

        # 检查是否有任何有效的提供商配置
        valid_providers = [
            "openai",
            "deepseek",
            "ollama",
            "gemini",
            "anthropic",
            "azure",
            "custom",
        ]
        for provider in valid_providers:
            if provider in llm_config:
                config = llm_config[provider]
                api_key = config.get("api_key")
                base_url = config.get("base_url")
                model = config.get("model")

                # 检查配置是否完整
                if not api_key or not base_url or not model:
                    continue

                # 如果是本地服务（ollama），api_key可以是"ollama"
                if (
                    "localhost" in base_url
                    or "127.0.0.1" in base_url
                    or "ollama" in base_url.lower()
                ):
                    return True

                return bool(api_key and base_url and model)

        return False
    except Exception:
        return False


async def _show_tools():
    """显示当前可用的MCP工具"""
    try:
        mgr = await MCPServerManager.get_instance()
        tools = await mgr.list_tools()
    except Exception as e:  # noqa: BLE001
        console.print(f"[red]Failed to fetch tools: {e}")
        return
    if not tools:
        console.print("[yellow]No tools available[/yellow]")
        return
    rows = [f"[bold]{t.name}[/bold]: {getattr(t, 'description', '')}" for t in tools]
    console.print(
        Panel("\n".join(rows), title=f"Tools ({len(rows)})", border_style="cyan")
    )


async def _cleanup_mcp():
    """清理MCP服务器管理器"""
    try:
        mgr = await MCPServerManager.get_instance()
        await mgr.cleanup()
    except Exception:  # noqa: BLE001
        # 忽略清理过程中的错误，避免干扰主程序退出
        pass


async def _interactive(
    model: Optional[str] = None,
    once: Optional[str] = None,
    quiet: bool = False,
    verbose: bool = False,
    debug: bool = False,
    human_approval: bool = False,
    confirm: bool = False,
    output_format: str = "text",
    timeout: int = 30,
):
    """交互式 CLI 主循环"""
    # 设置信号处理器
    signal_manager.setup_signal_handlers()

    # 确保 Agent kernel 可用
    try:
        await ensure_kernel()
        kernel_ref = get_kernel()  # 获取kernel实例以供后续使用
    except Exception:
        console.print("[red]初始化核心服务失败[/red]")
        raise typer.Exit(1)

    # 创建任务执行器
    task_executor = TaskExecutor(kernel_ref)
    
    active_model = current_model() or "unknown"
    if once:
        if verbose:
            cli_handler.print_banner(active_model, mode="once")
        try:
            res = await task_executor.run_agent_with_interrupt(
                once,
                stream=not quiet,
                capture_steps=debug,
                minimal=quiet or (not verbose and not debug),
            )
        except asyncio.CancelledError:
            # 任务被取消
            console.print("[yellow]任务已被停止[/yellow]")
            return
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Execution failed: {e}")
            return
        # 最终答案已经通过XML状态机流式输出，无需额外处理

        # 推理过程已经实时显示，不再重复显示
        return

    # 进入交互循环
    if verbose:
        cli_handler.print_banner(active_model, mode="chat")

    # 显示欢迎信息和logo
    console.clear()
    cli_handler.show_logo()
    console.print("[bold green]Welcome to Stock Agent CLI![/bold green]")
    console.print("[dim]Type /help for available commands, /quit to exit[/dim]\n")

    try:
        while True:
            try:
                user_input = await cli_session.prompt_user()
            except (EOFError, KeyboardInterrupt):
                console.print("\n[red]Exiting...[/red]")
                break
            if not user_input.strip():
                continue

            # 处理特殊命令 - 标准化命令格式
            cmd = user_input.strip().lower()
            if cmd in {"/quit", "/exit"}:
                console.print("[dim]Goodbye![/dim]")
                break
            elif cmd == "/tools":
                await _show_tools()
                continue
            elif cmd == "/status":
                cli_handler.show_status(active_model)
                continue
            elif cmd in {"/help", "/h"}:
                cli_handler.show_help(__version__)
                continue
            elif cmd == "/clear":
                console.clear()
                cli_handler.show_logo()
                console.print("[bold green]Welcome to Stock Agent CLI![/bold green]")
                console.print(
                    "[dim]Type /help for available commands, /quit to exit[/dim]\n"
                )
                continue
            elif cmd == "/version":
                console.print(f"Stock Agent CLI v{__version__}")
                continue

            console.print(Panel(user_input, title="Question", border_style="cyan"))
            console.print("[dim]💡 提示: 按 Ctrl+C 可以中断当前任务[/dim]")
            try:
                res = await task_executor.run_agent_with_interrupt(
                    user_input,
                    stream=not quiet,
                    capture_steps=debug,
                    minimal=quiet or (not verbose and not debug),
                    enable_interrupt=True,  # 在 chat 模式下启用中断
                    use_persistent_context=True,  # 在chat模式下使用持久上下文
                )
            except asyncio.CancelledError:
                # 任务被取消，已经在_run_agent_with_interrupt中处理了
                continue
            except Exception as e:  # noqa: BLE001
                console.print(f"[red]Execution failed: {e}")
                continue
            # 最终答案已经通过XML状态机流式输出，无需额外处理

            # 推理过程已经实时显示，不再重复显示
    finally:
        # 清理MCP资源
        await _cleanup_mcp()


@app.command()
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
) -> None:
    """单轮问答模式 - 向AI提出问题并获得答案"""
    # 设置信号处理器
    signal_manager.setup_signal_handlers()

    _setup_logging("DEBUG" if debug else "ERROR")

    # 检查并设置LLM配置
    config_file = config or "config/settings.yaml"
    if not _check_llm_config():
        console.print("[red]LLM配置不完整，请配置 config/settings.yaml[/red]")
        raise typer.Exit(1)

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
        )
    )


@app.command()
def chat(
    model: str = typer.Option("qwen2.5:7b", "--model", "-m", help="使用的模型名称"),
    minimal: bool = typer.Option(False, "--minimal", help="最小化输出"),
):
    """进入交互式聊天模式（具有记忆功能）"""
    # 设置信号处理器
    signal_manager.setup_signal_handlers()
    _setup_logging("ERROR")

    # 检查并设置LLM配置
    if not _check_llm_config():
        console.print("[red]LLM配置不完整，请配置 config/settings.yaml[/red]")
        raise typer.Exit(1)

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


@app.command()
def tools() -> None:
    """列出可用工具"""
    _setup_logging("ERROR")
    asyncio.run(_show_tools())


def main():
    """Entry point for stock-cli command."""
    app()


if __name__ == "__main__":  # pragma: no cover
    app()