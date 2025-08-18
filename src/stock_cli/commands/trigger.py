"""触发器命令"""
import asyncio
import typer
from rich.console import Console
from ..core.config_resolver import load_settings, resolve_settings_path
from ..triggers import get
# 确保触发器模块被导入
from ..triggers import ask_time
from ..tools.mcp_server_manager import MCPServerManager

console = Console()
app = typer.Typer()

@app.command()
def trigger(
    trigger_type: str = typer.Option(None, "--type", "-t", help="触发器类型"),
    session_id: str = typer.Option("default", "--session-id", "-s", help="会话ID"),
):
    """启动指定类型的触发器"""
    asyncio.run(main(trigger_type, session_id))


async def main(trigger_type: str, session_id: str):
    try:
        # 预先初始化 MCP 管理器，确保上下文在同一任务中进入与退出
        _ = await MCPServerManager.get_instance()
        if trigger_type:
            await _start_trigger_by_type(trigger_type, session_id)
        else:
            await _start_triggers_from_config(session_id)
    finally:
        await _cleanup_resources()


async def _start_trigger_by_type(trigger_type: str, session_id: str):
    """根据类型启动单个触发器"""
    trigger_func = get(trigger_type)
    if trigger_func:
        try:
            await trigger_func(session_id, {"interval_seconds": 30})
        except KeyboardInterrupt:
            console.print("\n[green]已正常退出[/green]")
        except Exception as e:
            console.print(f"\n[red]执行出错: {e}[/red]")
            raise typer.Exit(1)
    else:
        console.print(f"[red]未知的触发器类型: {trigger_type}[/red]")
        raise typer.Exit(1)


async def _start_triggers_from_config(session_id: str):
    try:
        settings_path = resolve_settings_path()
        settings = load_settings(settings_path)
        sessions_config = settings.get("sessions", {})
        session_config = sessions_config.get(session_id, {})
        if session_config.get("mode") != "trigger":
            console.print(f"[red]会话 {session_id} 不是触发器模式[/red]")
            raise typer.Exit(1)
        triggers = session_config.get("triggers", [])
        if not triggers:
            console.print(f"[yellow]会话 {session_id} 没有配置触发器[/yellow]")
            return
        console.print(f"[green]启动会话 {session_id} 的 {len(triggers)} 个触发器...[/green]")
        tasks = []
        for trigger_config in triggers:
            if not trigger_config.get("enabled", False):
                continue
            trigger_type = trigger_config.get("type")
            trigger_func = get(trigger_type)
            if trigger_func:
                task = asyncio.create_task(
                    trigger_func(session_id, trigger_config)
                )
                tasks.append(task)
            else:
                console.print(f"[yellow]未知的触发器类型: {trigger_type}[/yellow]")
        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                pass
        else:
            console.print("[yellow]没有启用的触发器[/yellow]")
        console.print("[green]所有触发器已停止[/green]")
    except Exception as e:
        console.print(f"[red]加载配置失败: {e}[/red]")
        raise typer.Exit(1)


async def _cleanup_resources():
    """清理MCP资源"""
    try:
        from ..tools.mcp_server_manager import MCPServerManager
        mgr = await MCPServerManager.get_instance()
        await mgr.cleanup()
    except Exception:
        pass