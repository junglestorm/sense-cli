"""定时询问时间的触发器示例"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any

from rich.console import Console

from . import register
from ..core.interaction import _run_agent_with_interrupt
from ..core.session import SessionManager

logger = logging.getLogger(__name__)


@register("ask_time")
async def ask_time_trigger(session_id: str, config: Dict[str, Any]):
    """定时询问时间的触发器
    
    Args:
        session_id: 会话ID
        config: 触发器配置
    """
    console = Console()
    interval = config.get("interval_seconds", 30)
    console.print(f"[green]启动定时询问时间触发器，每隔{interval}秒询问一次时间...[/green]")
    
    # 创建会话管理器实例
    session_manager = SessionManager()
    session = session_manager.get_session(session_id)
    
    try:
        while True:
            # 构造事件内容
            now = datetime.now()
            content = f"定时询问: 现在是 {now.strftime('%Y-%m-%d %H:%M:%S')}，请确认当前时间。"
            
            # 将问题添加到会话历史中，就像chat模式中用户输入一样
            session.append_qa({"role": "user", "content": content})
            
            # 打印问题，就像chat模式中显示用户输入一样
            console.print(f"\n[bold blue]stock-cli>[/bold blue] {content}")
            
            # 使用与chat命令完全相同的处理逻辑
            await _run_agent_with_interrupt(
                question=content,
                capture_steps=False,
                minimal=False,
                session_id=session_id,
            )
            
            # 等待指定间隔
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        logger.info(f"会话 {session_id} 的定时询问时间触发器被取消")
    except Exception as e:
        logger.error(f"会话 {session_id} 的定时询问时间触发器执行出错: {e}")