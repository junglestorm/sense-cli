"""工具命令"""

import asyncio
from rich.console import Console
from rich.panel import Panel

from ..logs.logger import configure_logging
from ..tools.mcp_server_manager import MCPServerManager

console = Console()


def tools() -> None:
    """列出可用工具"""
    configure_logging("ERROR", console=False)

    async def main():
        try:
            mgr = await MCPServerManager.get_instance()
            tool_list = await mgr.list_tools()
        except Exception as e:  # noqa: BLE001
            console.print(f"[red]Failed to fetch tools: {e}")
            return

        if not tool_list:
            console.print("[yellow]No tools available[/yellow]")
            return

        rows = [f"[bold]{t.name}[/bold]: {getattr(t, 'description', '')}" for t in tool_list]
        console.print(Panel("\n".join(rows), title=f"Tools ({len(rows)})", border_style="cyan"))

        # 退出时清理资源，避免 anyio cancel scope 报错
        try:
            await mgr.cleanup()
        except Exception:
            pass

    asyncio.run(main())