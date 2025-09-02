"""交互处理模块

处理CLI中的交互逻辑，包括单次问答和持续对话模式。
"""

import asyncio
import logging
import time
import traceback
from typing import Optional, List, Callable, Awaitable, Dict, Any

import typer
from rich import print
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML
from quote import quote

from ..agent.runtime import ensure_kernel, get_kernel, current_model
from ..core.session_manager import SessionManager
from ..utils.display import show_help, show_status, print_banner
from ..utils.redis_bus import RedisBus
from ..core.config_resolver import resolve_settings_path, load_settings

logger = logging.getLogger(__name__)
console = Console()

# 全局SessionManager实例
_session_manager = SessionManager()
_current_task: Optional[asyncio.Task] = None
_interrupt_requested = False



async def _run_agent_with_interrupt(
    question: str,
    *,
    capture_steps: bool = False,
    minimal: bool = False,
    session_id: str = "default",
    role_config: Optional[Dict[str, Any]] = None,
) -> dict:
    """运行Agent任务并支持中断"""
    global _current_task, _interrupt_requested

    _interrupt_requested = False
    kernel = await ensure_kernel(session_id=session_id, role_config=role_config)
    start_t = time.time()
    progress_lines: List[str] = []

    async def on_progress(chunk: str):
        # 检查是否收到中断请求
        if _interrupt_requested:
            raise asyncio.CancelledError("用户中断")

        if chunk.startswith("[Stream]"):
            text = chunk.replace("[Stream]", "")
            # 使用print直接输出，避免Rich的潜在截断问题
            print(text, end="", flush=True)
        elif not minimal and chunk.startswith("[StreamThinking]"):
            # 仅输出思考内容本身，不再为每个chunk重复打印“💭 thinking: ”前缀与换行
            text = chunk.replace("[StreamThinking]", "")
            console.print(f"[dim]{text}[/dim]", end="")
        elif not minimal and chunk.startswith("[StreamAction]"):
            text = chunk.replace("[StreamAction]", "")
            console.print(f"[dim]{text}[/dim]", end="")
        elif not minimal and chunk.startswith("[StreamObservation]"):
            text = chunk.replace("[StreamObservation]", "")
            console.print("\n[dim]🔎 observation:[/dim]", end="")
            console.print(f"[dim]{text}[/dim]", end="")
        elif not minimal and chunk.startswith("[ThinkingHeader]"):
            console.print("\n[dim]💭 thinking: [/dim]", end="")
        elif not minimal and chunk.startswith("[ActionHeader]"):
            console.print("\n[dim]⚡ action: [/dim]", end="")
        elif not minimal and chunk.startswith("[MonitorHeader]"):
            console.print("\n[dim]🔍 monitor: [/dim]", end="")
        elif not minimal and chunk.startswith("[FinalAnswerHeader]"):
            # 显示最终答案标题和上方横线
            title = "✅ 最终答案"
            console.print(f"\n{'─' * 50}")
            console.print(f"[bold green]{title}[/bold green]")
            console.print("─" * 50)
        elif not minimal and chunk.startswith("[StreamFinalAnswer]"):
            text = chunk.replace("[StreamFinalAnswer]", "")
            # 最终答案使用正常颜色显示，不用dim
            print(text, end="", flush=True)
        elif not minimal and chunk.startswith("[StreamMonitor]"):
            text = chunk.replace("[StreamMonitor]", "")
            console.print(f"[dim]{text}[/dim]", end="")
        elif not minimal and chunk.startswith("[FinalAnswerEnd]"):
            # 最终答案结束，显示下方横线
            console.print(f"\n{'─' * 50}")
        # 过滤掉原始的ReAct关键词
        if capture_steps and chunk.startswith("[StreamThinking]"):
            progress_lines.append(chunk)


    # 直接通过 Kernel.run 执行，保持统一入口（Kernel 内部负责 append_qa 与 Task 创建）
    _current_task = asyncio.create_task(
        kernel.run(
            question,
            progress_cb=on_progress,
            record_user_question=True,
        )
    )

    try:
        answer = await _current_task
        latency = time.time() - start_t

        # 获取当前请求的token使用量（使用tiktoken计算的上下文token）
        token_usage_info = {}
        if hasattr(kernel, '_current_request_token_usage'):
            token_usage_info = kernel._current_request_token_usage
        
        result = {
            "answer": answer,
            "model": kernel.llm_provider.model if kernel.llm_provider else "unknown",
            "latency": latency,
            "reasoning": progress_lines if capture_steps else [],
            "token_usage": token_usage_info,
        }

        return result

    except asyncio.CancelledError:
        # 任务被取消
        if _current_task:
            _current_task.cancel()
        raise
    except Exception as e:  # noqa: BLE001
        # 其余异常向上抛出，由调用侧统一处理
        raise
    finally:
        _current_task = None

async def _cleanup_mcp_resources():
    """优雅清理 MCP 资源，避免 anyio cancel scope 异常"""
    try:
        from ..tools.mcp_server_manager import MCPServerManager
        mgr = await MCPServerManager.get_instance()
        await mgr.cleanup()
    except Exception:
        # 清理失败不影响主流程
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
    session_id: str = "default",
    # ...existing code...
    role: Optional[str] = None,
):
    """交互式 CLI 主循环"""
    
    # 初始化role_config为None
    role_config = None

    # 确保 Agent kernel 可用
    try:
        await ensure_kernel(session_id=session_id, role_config=role_config)
        kernel_ref = get_kernel()  # 获取kernel实例以供后续使用
        # 预初始化 MCP 管理器，确保在同一任务中 enter/exit，避免 anyio cancel scope 错误
        try:
            from ..tools.mcp_server_manager import MCPServerManager
            await MCPServerManager.get_instance()
        except Exception:
            pass
    except Exception as e:
        console.print(f"[red]初始化核心服务失败: {e}[/red]")
        try:
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        except Exception:
            pass
        raise typer.Exit(1)

    # 注册在线会话并启动“会话收件箱”监控器（被动监听通信）
    inbox_monitor_task: Optional[asyncio.Task] = None
    other_monitor_tasks: List[asyncio.Task] = []

    async def _shutdown_inbox_and_unregister():
        nonlocal inbox_monitor_task, other_monitor_tasks
        try:
            if inbox_monitor_task:
                inbox_monitor_task.cancel()
                try:
                    await inbox_monitor_task
                except Exception:
                    pass
            # 停止其他监控器任务
            if other_monitor_tasks:
                for t in other_monitor_tasks:
                    try:
                        t.cancel()
                        await t  # 等待任务清理完成
                    except Exception:
                        pass
        finally:
            try:
                await RedisBus.unregister_session(session_id)
            except Exception:
                pass
            try:
                await RedisBus.cleanup()
            except Exception:
                pass

    # 标记会话在线
    try:
        await RedisBus.register_session(session_id)
    except Exception:
        pass

    # 初始化并启动监控器系统
    try:
        from ..core.monitor_manager import get_monitor_manager
        from ..monitors import register_all_monitors
        
        # 注册所有监控器
        await register_all_monitors()
        logger.info("监控器系统初始化完成")
        
        # 获取监控器管理器实例
        manager = await get_monitor_manager()
        
        # 启动会话收件箱监控器
        await manager.start_monitor("session_inbox", {"session_id": session_id})
        logger.info("会话收件箱监控器已启动")
        
    except ImportError as e:
        logger.error("监控器模块导入失败: %s", str(e))
    except Exception as e:
        logger.warning("监控器系统初始化失败: %s", e)
        logger.exception("详细错误信息:")


    active_model = current_model() or "unknown"
    if once:
        if verbose:
            print_banner(active_model, mode="once")
        try:
            res = await _run_agent_with_interrupt(
                once,  # 传递用户问题
                capture_steps=debug,
                minimal=quiet or (not verbose and not debug),
                session_id=session_id,
                role_config=role_config,
            )
        except asyncio.CancelledError:
            # 任务被取消
            console.print("[yellow]任务已被停止[/yellow]")
            # 继续进行资源清理
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Execution failed: {e}")
        finally:
            # 确保在一次性模式结束时优雅关闭 MCP，避免 anyio 作用域关闭报错
            try:
                from ..tools.mcp_server_manager import MCPServerManager
                mgr = await MCPServerManager.get_instance()
                await mgr.cleanup()
            except Exception:
                pass
            # 关闭收件箱并注销在线会话
            try:
                await _shutdown_inbox_and_unregister()
            except Exception:
                pass
        # 最终答案已经通过XML状态机流式输出，无需额外处理
        # 但显示token使用统计信息
        if res and 'token_usage' in res and res['token_usage']:
            token_info = res['token_usage']
            console.print(f"\n[dim]Token使用统计: context={token_info.get('context_tokens', 0)}, total={token_info.get('total_tokens', 0)}, prompt={token_info.get('prompt_tokens', 0)}, completion={token_info.get('completion_tokens', 0)}[/dim]")
  
        # 推理过程已经实时显示，不再重复显示
        return

    # 进入交互循环
    if verbose:
        print_banner(active_model, mode="chat")

    session = PromptSession(auto_suggest=AutoSuggestFromHistory())

    while True:
        try:
            user_input = await session.prompt_async(HTML('<ansicyan>stock-cli&gt; </ansicyan>'))
        except KeyboardInterrupt:
            bye = quote('inspire', limit=1)
            console.print(f"[yellow]{bye[0]['quote']}![/yellow]")
            try:
                await _cleanup_mcp_resources()
            except Exception:
                pass
            try:
                await _shutdown_inbox_and_unregister()
                # ...existing code...
            except Exception:
                pass
            break
        except EOFError:
            bye = quote('inspire', limit=1)
            console.print(f"[yellow]{bye[0]['quote']}![/yellow]")
            try:
                await _cleanup_mcp_resources()
            except Exception:
                pass
            try:
                await _shutdown_inbox_and_unregister()
                # ...existing code...
            except Exception:
                pass
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input in ["/quit", "/exit"]:
            bye = quote('inspire', limit=1)
            console.print(f"[yellow]{bye[0]['quote']}![/yellow]")
            try:
                await _cleanup_mcp_resources()
            except Exception:
                pass
            try:
                await _shutdown_inbox_and_unregister()
            except Exception:
                pass
            break
        elif user_input in ["/help", "/h"]:
            show_help()
            continue
        elif user_input == "/clear":
            console.clear()
            continue
        elif user_input == "/status":
            show_status()
            continue
        elif user_input == "/version":
            from ..cli import __version__
            console.print(f"Stock Agent CLI v{__version__}")
            continue
        elif user_input == "/reset":
            # 清空会话记忆
            try:
                from ..agent.runtime import get_session_manager
                session_manager = get_session_manager()
                current_session = session_manager.get_session(session_id)
                if current_session:
                    current_session.clear_context()
                    console.print("[green]✓ 会话记忆已清空[/green]")
                else:
                    console.print("[yellow]⚠ 当前会话不存在[/yellow]")
            except Exception as e:
                console.print(f"[red]✗ 清空记忆失败: {e}[/red]")
            continue

        try:
            res = await _run_agent_with_interrupt(
                user_input,
                capture_steps=debug,
                minimal=quiet or (not verbose and not debug),
                session_id=session_id,
                role_config=role_config,
            )
        except asyncio.CancelledError:
            # 任务被取消，已经在_run_agent_with_interrupt中处理了
            continue
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Execution failed: {e}")
            continue
        # 最终答案已经通过XML状态机流式输出，无需额外处理
        # 但显示token使用统计信息
        if res and 'token_usage' in res and res['token_usage']:
            token_info = res['token_usage']
            console.print(f"[dim]Token使用统计: total={token_info.get('total_tokens', 0)}, prompt={token_info.get('prompt_tokens', 0)}, completion={token_info.get('completion_tokens', 0)}[/dim]")

        # 推理过程已经实时显示，不再重复显示
        # 退出聊天循环后，优雅关闭 MCP 资源，避免 anyio cancel scope 异常
        try:
            await _cleanup_mcp_resources()
        except Exception:
            pass





