"""交互处理模块

处理CLI中的交互逻辑，包括单次问答和持续对话模式。
"""

import asyncio
import time
import traceback
from typing import Optional, List, Callable, Awaitable, Dict, Any

import typer
from rich import print
from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory

from ..agent.runtime import ensure_kernel, get_kernel, current_model
from ..core.session_manager import SessionManager
from ..utils.display import show_help, show_status, print_banner
from ..utils.redis_bus import RedisBus
from ..core.config_resolver import resolve_triggers_path, load_triggers_config, resolve_settings_path, load_settings

console = Console()

# 全局SessionManager实例
_session_manager = SessionManager()
_current_task: Optional[asyncio.Task] = None
_interrupt_requested = False

# 触发器任务管理器
_active_trigger_tasks: Dict[str, asyncio.Task] = {}
_trigger_configs: Dict[str, Dict[str, Any]] = {}


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

        result = {
            "answer": answer,
            "model": kernel.llm_provider.model if kernel.llm_provider else "unknown",
            "latency": latency,
            "reasoning": progress_lines if capture_steps else [],
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
    triggers: Optional[List[str]] = None,
    role: Optional[str] = None,
):
    """交互式 CLI 主循环"""
    # 加载角色配置
    role_config = None
    if role:
        try:
            # 加载设置文件获取角色配置
            settings_path = resolve_settings_path()
            settings = load_settings(settings_path)
            roles_config = settings.get("roles", {})
            
            # 加载所有角色配置
            _session_manager.load_role_configs(roles_config)
            
            # 获取指定角色配置
            role_config = _session_manager.get_role_config(role)
            if not role_config:
                console.print(f"[yellow]警告: 未找到角色 '{role}' 的配置[/yellow]")
            else:
                console.print(f"[green]已加载角色: {role}[/green]")
                
        except Exception as e:
            console.print(f"[yellow]警告: 加载角色配置失败: {e}[/yellow]")

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

    # 注册在线会话并启动“会话收件箱”触发器（被动监听通信）
    inbox_task: Optional[asyncio.Task] = None
    other_trigger_tasks: List[asyncio.Task] = []

    async def _shutdown_inbox_and_unregister():
        nonlocal inbox_task, other_trigger_tasks
        try:
            if inbox_task:
                inbox_task.cancel()
                try:
                    await inbox_task
                except Exception:
                    pass
            # 停止额外触发器
            if other_trigger_tasks:
                for t in other_trigger_tasks:
                    try:
                        t.cancel()
                    except Exception:
                        pass
                try:
                    await asyncio.gather(*other_trigger_tasks, return_exceptions=True)
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

    # 启动会话收件箱触发器（后台任务），仅当触发器已注册时
    try:
        from ..triggers import auto_discover, get as get_trigger
        auto_discover()
        inbox = get_trigger("session_inbox")
        if inbox:
            inbox_task = asyncio.create_task(inbox(session_id, {}))
            # 将自动启动的session_inbox也添加到全局管理器中
            _active_trigger_tasks["session_inbox"] = inbox_task
            _trigger_configs["session_inbox"] = {"session_id": session_id, "type": "session_inbox"}
    except Exception:
        # 忽略触发器启动失败，保持chat主流程
        pass

    # 若传入 --trigger 参数，则启动指定的触发器类型
    if triggers:
        try:
            from ..triggers import get as get_trigger
            for trigger_type in triggers:
                trigger_func = get_trigger(trigger_type)
                if trigger_func:
                    # 启动触发器，使用默认参数
                    other_trigger_tasks.append(asyncio.create_task(trigger_func(session_id, {})))
                    console.print(f"[green]已启动触发器: {trigger_type}[/green]")
                else:
                    console.print(f"[yellow]警告: 未找到触发器类型 '{trigger_type}'[/yellow]")
        except Exception as e:
            console.print(f"[yellow]启动触发器失败: {e}[/yellow]")

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
 
        # 推理过程已经实时显示，不再重复显示
        return

    # 进入交互循环
    if verbose:
        print_banner(active_model, mode="chat")

    session = PromptSession(auto_suggest=AutoSuggestFromHistory())

    while True:
        try:
            user_input = await session.prompt_async("stock-cli> ")
        except KeyboardInterrupt:
            console.print("\n[yellow]Bye![/yellow]")
            try:
                await _cleanup_mcp_resources()
            except Exception:
                pass
            try:
                await _shutdown_inbox_and_unregister()
                await _cleanup_all_triggers()
            except Exception:
                pass
            break
        except EOFError:
            console.print("\n[yellow]Bye![/yellow]")
            try:
                await _cleanup_mcp_resources()
            except Exception:
                pass
            try:
                await _shutdown_inbox_and_unregister()
                await _cleanup_all_triggers()
            except Exception:
                pass
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        if user_input in ["/quit", "/exit"]:
            console.print("[yellow]Bye![/yellow]")
            try:
                await _cleanup_mcp_resources()
            except Exception:
                pass
            try:
                await _shutdown_inbox_and_unregister()
                await _cleanup_all_triggers()
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
        elif user_input.startswith("/trigger"):
            await _handle_trigger_command(user_input, session_id)
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

        # 推理过程已经实时显示，不再重复显示
        # 退出聊天循环后，优雅关闭 MCP 资源，避免 anyio cancel scope 异常
        try:
            await _cleanup_mcp_resources()
        except Exception:
            pass


async def _handle_trigger_command(command: str, session_id: str = "default") -> None:
    """处理 /trigger 命令"""
    from rich.table import Table
    
    parts = command.split()
    if len(parts) < 2:
        console.print("[yellow]用法: /trigger [start|stop|list|status] [trigger_name]")
        console.print("[yellow]示例:")
        console.print("[yellow]  /trigger list - 列出所有可用触发器")
        console.print("[yellow]  /trigger start timer_5min - 启动定时器触发器")
        console.print("[yellow]  /trigger stop timer_5min - 停止定时器触发器")
        console.print("[yellow]  /trigger status - 显示触发器状态")
        return
    
    action = parts[1].lower()
    
    if action == "list":
        # 列出所有可用触发器
        from ..triggers import discover_triggers
        triggers = discover_triggers()
        
        table = Table(title="可用触发器")
        table.add_column("名称", style="cyan")
        table.add_column("类型", style="green")
        table.add_column("描述", style="white")
        
        for trigger_name, trigger_cls in triggers.items():
            table.add_row(trigger_name, trigger_cls.__name__, getattr(trigger_cls, "__doc__", "无描述") or "无描述")
        
        console.print(table)
        
    elif action == "start":
        if len(parts) < 3:
            console.print("[red]错误: 需要指定触发器名称")
            return
        
        trigger_name = parts[2]
        await _start_trigger(trigger_name, session_id)
        
    elif action == "stop":
        if len(parts) < 3:
            console.print("[red]错误: 需要指定触发器名称")
            return
        
        trigger_name = parts[2]
        await _stop_trigger(trigger_name)
        
    elif action == "status":
        await _show_trigger_status()
        
    else:
        console.print(f"[red]错误: 未知操作 '{action}'")


async def _start_trigger(trigger_name: str, session_id: str = "default") -> None:
    """启动指定触发器"""
    from ..triggers import discover_triggers
    
    triggers = discover_triggers()
    if trigger_name not in triggers:
        console.print(f"[red]错误: 找不到触发器 '{trigger_name}'")
        return
    
    # 检查是否已经启动
    if trigger_name in _active_trigger_tasks:
        console.print(f"[yellow]警告: 触发器 '{trigger_name}' 已经在运行")
        return
    
    # 使用默认配置而不是配置文件
    trigger_config = {"session_id": session_id}
    
    trigger_func = triggers[trigger_name]
    try:
        # 对于函数类型的触发器，直接调用
        if callable(trigger_func):
            task = asyncio.create_task(trigger_func(session_id=session_id, config=trigger_config))
            _active_trigger_tasks[trigger_name] = task
            _trigger_configs[trigger_name] = trigger_config
            console.print(f"[green]已启动触发器: {trigger_name}")
        else:
            console.print(f"[red]错误: 触发器 '{trigger_name}' 不是可调用函数")
    except Exception as e:
        console.print(f"[red]启动触发器失败: {e}")


async def _stop_trigger(trigger_name: str) -> None:
    """停止指定触发器"""
    if trigger_name not in _active_trigger_tasks:
        console.print(f"[yellow]警告: 触发器 '{trigger_name}' 未在运行")
        return
    
    task = _active_trigger_tasks[trigger_name]
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception as e:
        console.print(f"[yellow]停止触发器时出现异常: {e}")
    
    del _active_trigger_tasks[trigger_name]
    if trigger_name in _trigger_configs:
        del _trigger_configs[trigger_name]
    
    console.print(f"[green]已停止触发器: {trigger_name}")


async def _show_trigger_status() -> None:
    """显示触发器状态"""
    from rich.table import Table
    
    table = Table(title="触发器状态")
    table.add_column("名称", style="cyan")
    table.add_column("状态", style="green")
    table.add_column("类型", style="yellow")
    
    # 显示正在运行的触发器
    for trigger_name in _active_trigger_tasks:
        config = _trigger_configs.get(trigger_name, {})
        trigger_type = config.get("type", "unknown")
        table.add_row(trigger_name, "运行中", trigger_type)
    
    # 显示所有可用的触发器类型
    from ..triggers import auto_discover, discover_triggers
    auto_discover()  # 确保所有触发器都已注册
    available_triggers = discover_triggers()
    for trigger_name in available_triggers:
        if trigger_name not in _active_trigger_tasks:
            table.add_row(trigger_name, "已停止", "触发器")
    
    console.print(table)


async def _cleanup_all_triggers() -> None:
    """清理所有触发器任务"""
    for trigger_name, task in list(_active_trigger_tasks.items()):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
        del _active_trigger_tasks[trigger_name]
    
    _trigger_configs.clear()

