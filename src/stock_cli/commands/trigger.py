"""触发器命令"""
import asyncio
from typing import Optional
import typer
from rich.console import Console
from ..core.config_resolver import (
    load_settings,
    resolve_settings_path,
    resolve_triggers_path,
    load_triggers_config,
)
from ..triggers import get, list_triggers, auto_discover
from ..tools.mcp_server_manager import MCPServerManager

console = Console()
app = typer.Typer()

@app.command()
def trigger(
    trigger_type: str = typer.Option(None, "--type", "-t", help="触发器类型"),
    session_id: str = typer.Option("default", "--session-id", "-s", help="会话ID"),
    config_path: Optional[str] = typer.Option(None, "--config", help="主配置文件路径（可选）"),
    triggers_path: Optional[str] = typer.Option(None, "--triggers", help="触发器配置文件路径（优先使用）"),
):
    """启动指定类型的触发器"""
    asyncio.run(main(trigger_type, session_id, config_path, triggers_path))


async def main(trigger_type: str, session_id: str, config_path: Optional[str], triggers_path: Optional[str]):
    try:
        # 自动发现触发器模块，避免入口与具体实现耦合
        auto_discover()
        # 预先初始化 MCP 管理器，确保上下文在同一任务中进入与退出
        _ = await MCPServerManager.get_instance()
        # 诊断日志：显示当前已注册的触发器（用于验证是否依赖显式导入）
        console.print(f"[cyan]已注册触发器: {', '.join(list_triggers()) or '(none)'}[/cyan]")
        if trigger_type:
            await _start_trigger_by_type(trigger_type, session_id)
        else:
            await _start_triggers_from_config(session_id, config_path, triggers_path)
    finally:
        await _cleanup_resources()


async def _start_trigger_by_type(trigger_type: str, session_id: str):
    """根据类型启动单个触发器"""
    trigger_func = get(trigger_type)
    if trigger_func:
        try:
            # 只传递 session_id 和空 config，定时等逻辑由 trigger 内部决定（诊断日志）
            console.print("[blue]入口层按类型启动：不注入定时参数，config = {}[/blue]")
            await trigger_func(session_id, {})
        except KeyboardInterrupt:
            console.print("\n[green]已正常退出[/green]")
        except Exception as e:
            console.print(f"\n[red]执行出错: {e}[/red]")
            raise typer.Exit(1)
    else:
        console.print(f"[red]未知的触发器类型: {trigger_type}[/red]")
        raise typer.Exit(1)


async def _start_triggers_from_config(session_id: str, config_path: Optional[str], triggers_path: Optional[str]):
    try:
        # 优先：独立触发器配置文件（--triggers 或默认 config/triggers.yaml）
        try:
            t_path = resolve_triggers_path(triggers_path)
            t_conf = load_triggers_config(t_path)
            trig_list = t_conf.get("triggers", [])
            if not isinstance(trig_list, list):
                raise ValueError("triggers.yaml: 'triggers' 必须是列表")
            if trig_list:
                console.print(f"[green]使用独立触发器配置: {t_path} 共 {len(trig_list)} 个触发器[/green]")
                tasks = []
                for spec in trig_list:
                    if not spec.get("enabled", False):
                        continue
                    t_type = spec.get("type")
                    trigger_func = get(t_type)
                    if trigger_func:
                        params = spec.get("params", {})  # 所有策略参数由 trigger 内部使用
                        task = asyncio.create_task(trigger_func(session_id, params))
                        tasks.append(task)
                    else:
                        console.print(f"[yellow]未知的触发器类型: {t_type}[/yellow]")
                if tasks:
                    try:
                        await asyncio.gather(*tasks, return_exceptions=True)
                    except asyncio.CancelledError:
                        pass
                else:
                    console.print("[yellow]没有启用的触发器[/yellow]")
                console.print("[green]所有触发器已停止[/green]")
                return
        except Exception as e:
            console.print(f"[yellow]未找到或加载独立触发器配置，回退至 settings.sessions: {e}[/yellow]")

        # 回退：读取 settings.yaml 中与 session 绑定的触发器清单（兼容旧配置，打印废弃提示）
        settings_path = resolve_settings_path(config_path)
        settings = load_settings(settings_path)
        sessions_config = settings.get("sessions", {})
        session_config = sessions_config.get(session_id, {})
        console.print(f"[magenta]DEPRECATED: 使用基于 session 的 triggers 配置: session_id={session_id}，建议改用 --triggers[/magenta]")
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
            t_type = trigger_config.get("type")
            trigger_func = get(t_type)
            if trigger_func:
                task = asyncio.create_task(trigger_func(session_id, trigger_config))
                tasks.append(task)
            else:
                console.print(f"[yellow]未知的触发器类型: {t_type}[/yellow]")
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