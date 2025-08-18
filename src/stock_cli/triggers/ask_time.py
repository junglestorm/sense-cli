"""定时询问时间的触发器示例"""

import asyncio
import logging
from datetime import datetime
from typing import Tuple, Optional

from rich.console import Console

from . import register
from ..core.interaction import _run_agent_with_interrupt
from ..core.session import SessionManager

logger = logging.getLogger(__name__)

@register("ask_time")
def build_ask_time(spec: dict) -> Tuple[str, str, Optional[str]]:
    """
    构造一个询问时间的任务
    
    Args:
        spec: 来自配置文件的触发器配置
        
    Returns:
        tuple: (role, content, task_template)
    """
    # 获取配置参数
    prefix = spec.get("prefix", "现在是")
    timezone = spec.get("timezone", "UTC")
    
    # 构造内容
    content = f"{prefix}什么时间？请使用 {timezone} 时区。"
    
    # 返回角色、内容和任务模板（可选）
    return ("scheduler", content, spec.get("task_template"))


async def run_scheduler():
    """运行定时调度器，每隔30秒询问一次时间"""
    console = Console()
    console.print("[green]启动定时询问时间触发器，每隔30秒询问一次时间...[/green]")
    
    # 创建会话管理器实例
    session_manager = SessionManager()
    session = session_manager.get_session("default")
    
    try:
        while True:
            # 构造事件内容
            now = datetime.now()
            content = f"定时询问: 请确认当前时间。"
            
            # 将问题添加到会话历史中，就像chat模式中用户输入一样
            session.append_qa({"role": "user", "content": content})
            
            # 打印问题，就像chat模式中显示用户输入一样
            console.print(f"\n[bold blue]stock-cli>[/bold blue] {content}")
            
            # 使用与chat命令完全相同的处理逻辑
            await _run_agent_with_interrupt(
                question=content,
                capture_steps=False,
                minimal=False,  # 改为False以显示完整输出
                session_id="default",
            )
            
            # 等待30秒
            await asyncio.sleep(30)
    except asyncio.CancelledError:
        logger.info("定时询问时间触发器被取消")
    except Exception as e:
        logger.error(f"定时询问时间触发器执行出错: {e}")
    finally:
        # 清理资源
        await _cleanup_resources()


async def _cleanup_resources():
    """清理MCP资源"""
    try:
        from ..tools.mcp_server_manager import MCPServerManager
        mgr = await MCPServerManager.get_instance()
        await mgr.cleanup()
    except Exception as e:
        logger.debug(f"资源清理时出错: {e}")