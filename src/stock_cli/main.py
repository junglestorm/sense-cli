"""Stock Agent CLI (MVP)

特性 (聚焦 Agent 能力 / 类 Gemini CLI 体验):
    - ask: 单轮问答, 支持 --model 覆盖, --json 结构化输出, --show-thought 显示推理阶段
    - chat: 多轮对话 (首轮流式输出)

JSON 输出结构: {"answer","model","latency","reasoning"}
"""

from __future__ import annotations

import asyncio
import logging
import time
import sys
import signal
from typing import Optional, List, Dict, Any
from pathlib import Path

import typer
from rich import print
from rich.panel import Panel
from rich.console import Console
import yaml
from pyfiglet import Figlet
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from .agent.runtime import ensure_kernel, current_model
from .tools.mcp_server_manager import MCPServerManager

app = typer.Typer(add_completion=False, help="Stock Agent CLI - AI驱动的股票分析工具")
console = Console()

__version__ = "1.0.0"


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


# 全局变量用于存储当前运行的任务
_current_task: Optional[asyncio.Task] = None
_interrupt_requested: bool = False

# 全局变量用于存储持久的对话上下文
_persistent_context: Dict[str, Any] = {}

# 创建PromptSession实例以支持中文输入
session = PromptSession(
    history=FileHistory("data/history.txt"),
    auto_suggest=AutoSuggestFromHistory(),
)


def _setup_logging(level: str = "INFO"):
    """设置日志配置，只输出到文件，不输出到控制台"""
    # 创建日志目录
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # 完全清除现有的日志处理器
    logging.getLogger().handlers.clear()

    # 配置根日志只输出到文件
    logging.basicConfig(
        level=logging.ERROR,  # 提高阈值，减少日志输出
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%m/%d/%y %H:%M:%S",
        handlers=[
            logging.FileHandler("data/logs/agent.log", encoding="utf-8"),
        ],
        force=True,  # 强制重新配置
    )

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


def _print_banner(model: str, mode: str):
    # 仅在 verbose 模式调用
    line = f"model={model} mode={mode}"
    console.print(f"[dim]{line}[/dim]")


def _format_reasoning(lines: List[str]) -> List[str]:
    out: List[str] = []
    for ln in lines:
        if ln.startswith("[Agent]"):
            out.append(f"[cyan]> {ln.replace('[Agent]', '').strip()}[/cyan]")
        elif ln.startswith("[ReAct]"):
            core = ln.replace("[ReAct]", "").strip()
            out.append(f"[dim]• {core}[/dim]")
    return out


def _show_logo():
    """显示专业风格的logo"""
    f = Figlet(font="slant", width=120)
    logo_text = f.renderText("Stock Agent CLI")
    console.print(f"[bold blue]{logo_text}[/bold blue]")
    console.print(
        "[green]AI-Powered Stock Analysis Tool powered by ReAct Architecture[/green]\n"
    )


def _show_help():
    """显示帮助信息"""
    help_text = f"""
[bold blue]Stock Agent CLI v{__version__} - 帮助[/bold blue]

[yellow]基本用法:[/yellow]
  直接输入问题与AI对话，所有模式都会显示AI的思考过程

[yellow]中断功能:[/yellow]
  在任何模式下，当 AI 正在思考或生成答案时：
  • 按 Ctrl+C 可以中断当前任务
  • 中断后可以立即输入新的问题
  
[yellow]特殊命令:[/yellow]
  /help, /h      - 显示此帮助信息
  /tools         - 列出可用工具
  /status        - 显示系统状态  
  /clear         - 清屏
  /version       - 显示版本信息
  /quit, /exit   - 退出程序

[yellow]示例问题:[/yellow]
  分析一下阿里巴巴的股价走势
  帮我查找最近的股市新闻
  比较一下腾讯和阿里巴巴的财务数据

[yellow]命令行选项:[/yellow]
  --help         - 显示命令帮助
  --version, -V  - 显示版本信息
  --debug, -d    - 显示调试信息
  --no-color     - 禁用彩色输出
"""
    console.print(help_text.strip())


def _show_status():
    """显示系统状态"""
    try:
        model = current_model()
        status = "Active" if model else "Check configuration"
        model_name = model or "Check configuration"

        status_text = f"""
Status: {status}
Model: {model_name}
Services: Running
"""
        console.print(status_text.strip())
    except Exception:
        console.print("Status: Unable to determine")


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


def _signal_handler(signum, frame):
    """信号处理函数，用于处理 Ctrl+C"""
    global _interrupt_requested, _current_task

    if _current_task and not _current_task.done():
        console.print("\n[yellow]🛑 收到中断信号，正在停止当前任务...[/yellow]")
        _interrupt_requested = True
        _current_task.cancel()
    else:
        # 如果没有正在运行的任务，直接退出
        console.print("\n[red]Exiting...[/red]")
        sys.exit(0)


def _setup_signal_handlers():
    """设置信号处理器"""
    signal.signal(signal.SIGINT, _signal_handler)  # Ctrl+C


async def _run_agent_with_interrupt(
    question: str,
    *,
    stream: bool = True,
    capture_steps: bool = False,
    minimal: bool = False,
    enable_interrupt: bool = False,
    use_persistent_context: bool = False,
) -> dict:
    """运行单个 Agent 任务并返回结果/推理摘要，支持运行时中断。"""
    global _current_task, _interrupt_requested, _persistent_context

    # 重置中断标志
    _interrupt_requested = False

    kernel = await ensure_kernel()
    start_t = time.time()
    progress_lines: List[str] = []

    # 定义进度回调函数
    async def on_progress(chunk: str):
        # 检查是否收到中断请求
        if _interrupt_requested:
            raise asyncio.CancelledError("用户中断")

        if chunk.startswith("[Stream]"):
            text = chunk.replace("[Stream]", "")
            # 使用print直接输出，避免Rich的潜在截断问题
            print(text, end="", flush=True)
        elif not minimal and chunk.startswith("[StreamThought]"):
            text = chunk.replace("[StreamThought]", "")
            console.print(f"[dim]{text}[/dim]", end="", highlight=False)
        elif not minimal and chunk.startswith("[StreamAction]"):
            text = chunk.replace("[StreamAction]", "")
            console.print(f"[dim]{text}[/dim]", end="")
        elif not minimal and chunk.startswith("[ThoughtHeader]"):
            console.print("\n[dim]💭 thinking: [/dim]", end="")
        elif not minimal and chunk.startswith("[ActionHeader]"):
            console.print("\n[dim]⚡ action: [/dim]", end="")
        elif not minimal and chunk.startswith("[FinalAnswerHeader]"):
            # 显示最终答案标题和上方横线
            title = "✅ 最终答案"
            console.print(f"\n[bold green]{title}[/bold green]")
            console.print("─" * 50)
        elif not minimal and chunk.startswith("[StreamFinalAnswer]"):
            text = chunk.replace("[StreamFinalAnswer]", "")
            # 最终答案使用正常颜色显示，不用dim
            print(text, end="", flush=True)
        elif not minimal and chunk.startswith("[FinalAnswerEnd]"):
            # 最终答案结束，显示下方横线
            console.print(f"\n{'─' * 50}")
        elif not minimal and chunk.startswith("[StreamThought]"):
            text = chunk.replace("[StreamThought]", "")
            console.print(f"[dim]{text}[/dim]", end="")
        elif not minimal and chunk.startswith("[Thought]"):
            console.print(
                f"\n[dim]💭 thinking: {chunk.replace('[Thought]', '').strip()}[/dim]"
            )
        elif not minimal and chunk.startswith("[Action]"):
            console.print(
                f"\n[dim]⚡ action: {chunk.replace('[Action]', '').strip()}[/dim]"
            )
        # 过滤掉原始的ReAct关键词
        elif not minimal and chunk.strip() in ["Action", "Thought", "Final Answer"]:
            pass  # 忽略这些原始关键词
        if capture_steps and (
            chunk.startswith("[Thought]") or chunk.startswith("[Action]")
        ):
            progress_lines.append(chunk)

    from .core.types import Task

    # 根据模式决定使用什么上下文
    if use_persistent_context:
        # chat 模式：使用持久上下文
        if "conversation_history" not in _persistent_context:
            _persistent_context["conversation_history"] = []

        # 将当前问题添加到对话历史
        _persistent_context["conversation_history"].append(
            {"role": "user", "content": question}
        )

        task = Task(description=question, context=_persistent_context)
    else:
        # ask 模式：使用空上下文
        task = Task(description=question, context={})

    # 创建 agent 执行任务
    _current_task = asyncio.create_task(
        kernel.execute_task(task, progress_cb=on_progress, stream=stream)
    )

    try:
        # 等待任务完成
        answer = await _current_task

        # 如果使用持久上下文，保存AI的回答到对话历史
        if use_persistent_context and answer:
            _persistent_context["conversation_history"].append(
                {"role": "assistant", "content": answer}
            )

            # 限制对话历史长度，避免上下文过长
            max_history_pairs = 8  # 保留最近8轮对话（16条消息）
            if len(_persistent_context["conversation_history"]) > max_history_pairs * 2:
                # 保留最新的对话，删除最旧的
                _persistent_context["conversation_history"] = _persistent_context[
                    "conversation_history"
                ][-(max_history_pairs * 2) :]

    except asyncio.CancelledError:
        if _interrupt_requested:
            console.print("\n[yellow]🛑 任务已被用户中断[/yellow]")
        else:
            console.print("\n[yellow]任务已被停止[/yellow]")
        raise
    finally:
        _current_task = None
        _interrupt_requested = False

    latency = round(time.time() - start_t, 3)
    reasoning_fmt = _format_reasoning(progress_lines)
    token_usage = task.context.get("token_usage") or {}

    return {
        "answer": answer,
        "model": current_model(),
        "latency": latency,
        "reasoning": reasoning_fmt,
        "_raw_reasoning": progress_lines,
        "tokens": token_usage,
    }


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
    _setup_signal_handlers()

    # 确保 Agent kernel 可用，启用Human-in-the-Loop（如果需要）
    try:
        await ensure_kernel(
            enable_human_loop=human_approval,
            console=console,
            require_final_approval=confirm,
        )
    except Exception:
        console.print("[red]初始化核心服务失败[/red]")
        raise typer.Exit(1)

    active_model = current_model() or "unknown"
    if once:
        if verbose:
            _print_banner(active_model, mode="once")
        try:
            res = await _run_agent_with_interrupt(
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
        _print_banner(active_model, mode="chat")

    # 显示欢迎信息和logo
    console.clear()
    _show_logo()
    console.print("[bold green]Welcome to Stock Agent CLI![/bold green]")
    console.print("[dim]Type /help for available commands, /quit to exit[/dim]\n")

    try:
        while True:
            try:
                user_input = await session.prompt_async(
                    "> ",
                    enable_history_search=True,
                )
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
                _show_status()
                continue
            elif cmd in {"/help", "/h"}:
                _show_help()
                continue
            elif cmd == "/clear":
                console.clear()
                _show_logo()
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
                res = await _run_agent_with_interrupt(
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
    _setup_signal_handlers()

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
    _setup_signal_handlers()
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


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """默认进入对话模式"""
    if ctx.invoked_subcommand is None:
        # 检查并设置LLM配置
        if not _check_llm_config():
            console.print("[red]LLM配置不完整，请配置 config/settings.yaml[/red]")
            raise typer.Exit(1)

        _setup_logging("ERROR")
        asyncio.run(_interactive())


def main():
    """Entry point for stock-cli command."""
    app()


if __name__ == "__main__":  # pragma: no cover
    app()
