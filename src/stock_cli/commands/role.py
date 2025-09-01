"""角色会话管理命令"""

import typer
from rich.console import Console
from rich.table import Table

from ..core.session_manager import SessionManager
from ..utils.redis_bus import RedisBus

app = typer.Typer()
console = Console()

@app.command()
def list():
    """列出当前活动的带有角色的会话"""
    import asyncio
    session_manager = SessionManager()
    
    # 获取Redis中的活动会话
    active_sessions = asyncio.run(RedisBus.list_active_sessions())
    
    active_sessions_with_roles = []
    
    for session_id in active_sessions:
        # 尝试从会话文件中恢复角色信息
        session = session_manager.get_session(session_id)
        
        # 如果会话有角色配置但role_name为None，尝试重新加载
        if hasattr(session, 'role_config') and session.role_config and (not hasattr(session, 'role_name') or not session.role_name):
            # 从role_config中提取角色名称
            if 'name' in session.role_config:
                session.role_name = session.role_config['name']
        
        if hasattr(session, 'role_name') and session.role_name:
            active_sessions_with_roles.append({
                'session_id': session_id,
                'role_name': session.role_name,
                'role_config': session.role_config
            })
    
    if not active_sessions_with_roles:
        console.print("[yellow]没有找到任何带有角色的活动会话[/yellow]")
        return
    
    table = Table(title="活动角色会话", show_header=True, header_style="bold magenta")
    table.add_column("会话ID", style="cyan")
    table.add_column("角色名称", style="green")
    table.add_column("MCP工具", style="blue")
    
    for session_info in active_sessions_with_roles:
        role_config = session_info['role_config']
        if role_config and isinstance(role_config, dict):
            mcp_tools = ", ".join(role_config.get('allowed_mcp_servers', []))
            table.add_row(
                session_info['session_id'],
                session_info['role_name'],
                mcp_tools,
            )
        else:
            table.add_row(
                session_info['session_id'],
                session_info['role_name'],
                "无配置",
                "无配置"
            )
    
    console.print(table)

@app.command()
def show(session_id: str):
    """显示指定会话的角色详细信息"""
    session_manager = SessionManager()
    
    try:
        session = session_manager.get_session(session_id)
        if not hasattr(session, 'role_name') or not session.role_name:
            console.print(f"[yellow]会话 '{session_id}' 没有分配角色[/yellow]")
            return
        
        role_config = session.role_config
        if not role_config:
            console.print(f"[yellow]会话 '{session_id}' 的角色配置为空[/yellow]")
            return
        
        console.print(f"[bold cyan]会话ID:[/bold cyan] {session_id}")
        console.print(f"[bold cyan]角色名称:[/bold cyan] {session.role_name}")
        
        if 'description' in role_config:
            console.print(f"[bold cyan]描述:[/bold cyan] {role_config['description']}")
        
        if 'allowed_mcp_servers' in role_config:
            console.print(f"[bold cyan]MCP工具:[/bold cyan] {', '.join(role_config['allowed_mcp_servers'])}")
        
        
        if 'permissions' in role_config:
            console.print(f"[bold cyan]权限:[/bold cyan] {role_config['permissions']}")
        
        if 'system_prompt' in role_config:
            console.print("\n[bold cyan]系统提示词:[/bold cyan]")
            console.print(role_config['system_prompt'])
            
    except Exception as e:
        console.print(f"[red]获取会话信息失败: {e}[/red]")

if __name__ == "__main__":
    app()