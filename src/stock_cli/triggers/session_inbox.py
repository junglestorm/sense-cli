"""会话收件箱触发器：监听当前会话的消息通道并被动触发模型响应"""

import asyncio
import logging
from typing import Dict, Any

from rich.console import Console

from . import register
from ..utils.redis_bus import RedisBus
from ..core.session import SessionManager
from ..core.interaction import _run_agent_with_interrupt

logger = logging.getLogger(__name__)


@register("session_inbox")
async def session_inbox_trigger(session_id: str, config: Dict[str, Any]):
    """
    监听会话消息通道（基于轻量消息总线），收到消息后：
    - 以“用户消息”形式注入会话上下文
    - 复用 chat 的执行链路驱动模型响应
    """
    console = Console()
    console.print(f"[green]启动会话收件箱触发器：session={session_id}[/green]")

    # 标记当前会话在线
    try:
        await RedisBus.register_session(session_id)
    except Exception as e:
        logger.warning("注册在线会话失败 session_id=%s err=%r", session_id, e)

    session = SessionManager().get_session(session_id)

    async def _handle_message(obj: Dict[str, Any]):
        from_sid = str(obj.get("from") or "")
        content = str(obj.get("message") or "")
        
        # 修复：忽略来自自身会话的消息，避免自引用循环
        if not content or from_sid == session_id:
            return
            
        # 构造用户可见的注入消息，保持与 chat 输入一致的表现
        incoming = f"[来自 {from_sid or 'unknown'}] {content}"
        session.append_qa({"role": "user", "content": incoming})
        console.print(f"\n[bold blue]stock-cli>[/bold blue] {incoming}")
        # 复用 chat 的执行入口，驱动 kernel 执行
        await _run_agent_with_interrupt(
            question=incoming,
            capture_steps=False,
            minimal=False,
            session_id=session_id,
        )

    try:
        async for msg in RedisBus.subscribe_messages(session_id):
            try:
                await _handle_message(msg)
            except asyncio.CancelledError:
                raise
            except Exception as ie:
                logger.error("处理会话收件箱消息失败: %r", ie)
                await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        logger.info("会话收件箱触发器被取消: %s", session_id)
    except Exception as e:
        logger.error("会话收件箱触发器异常 session_id=%s err=%r", session_id, e)
    finally:
        try:
            await RedisBus.unregister_session(session_id)
        except Exception:
            pass