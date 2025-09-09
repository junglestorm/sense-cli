"""会话收件箱监控器：监听当前会话的消息通道并被动触发模型响应"""

import asyncio
import logging
from typing import Dict, Any

from rich.console import Console

from ..core.monitor_manager import Monitor, get_monitor_manager
from ..utils.redis_bus import RedisBus
from ..core.session import SessionManager
from ..core.interaction import _run_agent_with_interrupt
from ..core.session_lock import get_session_lock

logger = logging.getLogger(__name__)

async def session_inbox_monitor(arguments: Dict[str, Any]):
    """
    监听会话消息通道（基于轻量消息总线），收到消息后：
    - 以"用户消息"形式注入会话上下文
    - 复用 chat 的执行链路驱动模型响应
    """
    session_id = arguments.get("session_id", "default")
    console = Console()
    console.print(f"[green]启动会话收件箱监控器：session={session_id}[/green]")
    logger.info("启动会话收件箱监控器：session=%s", session_id)

    # 标记当前会话在线
    try:
        await RedisBus.register_session(session_id)
        logger.info("成功注册会话到Redis: %s", session_id)
    except Exception as e:
        logger.warning("注册在线会话失败 session_id=%s err=%r", session_id, e)

    session = SessionManager().get_session(session_id)
    logger.info("获取会话实例成功: %s", session_id)

    # 保持监控器运行状态的主循环
    async def _handle_message(obj: Dict[str, Any]):
        # 提取消息字段并进行基本验证
        from_sid = str(obj.get("from") or "")
        to_sid = str(obj.get("to") or "")
        
        # 确保消息内容存在且为字符串类型
        if "message" not in obj:
            logger.info("忽略缺少消息体的消息")
            return
            
        content = str(obj["message"])
        
        # 进一步验证消息内容是否为空
        if not content.strip():
            logger.info("忽略空白消息内容")
            return
        
        logger.info("收到消息: from=%s, to=%s, content=%s, obj=%s", from_sid, to_sid, content, obj)
        
        # 保持与会话ID的验证逻辑
        if to_sid and to_sid != session_id:
            logger.info("忽略非本会话消息: to_sid=%s, session_id=%s", to_sid, session_id)
            return
            
        # 防止自引用：如果发送者就是当前会话，忽略消息
        if from_sid and from_sid == session_id:
            logger.info("忽略自引用消息: from_sid=%s, session_id=%s", from_sid, session_id)
            return
            
        # 构造用户可见的注入消息，保持与 chat 输入一致的表现
        incoming = f"[来自 {from_sid or 'unknown'}] {content}"

        # 等待会话级锁释放后再打印/注入会话内容，避免在上一个任务仍在运行时提前打印。
        # 注意：这里短暂 acquire() -> release() 只是等待锁的可用性，但不在 inbox 中持有锁，
        # 否则会与后续 _run_agent_with_interrupt() 中对同一锁的 acquire() 导致死锁。
        try:
            lock = get_session_lock(session_id)
            # 如果锁被占用则等待；如果当前未被占用，acquire() 会立即返回。
            await lock.acquire()
            # 立即释放，表示我们观察到会话当前处于空闲状态。
            lock.release()
        except asyncio.CancelledError:
            # 如果监控任务被取消，则不继续处理此消息
            logger.info("waiting for session lock was cancelled: session=%s", session_id)
            raise
        except Exception:
            # 出于稳健性考虑，如果检查锁失败也不阻塞处理，回退为立即显示
            logger.exception("error while waiting for session lock, proceeding to print message")

        # 现在注入并打印（这时会话处于空闲或已恢复空闲）
        session.append_qa({"role": "user", "content": content})  # 直接使用原始内容
        console.print(f"\n[bold blue]stock-cli>[/bold blue] {incoming}")
        
        # 添加调试信息
        logger.debug("处理外部消息: %s -> %s: %s", from_sid, session_id, content)
        
        # 复用 chat 的执行入口，驱动 kernel 执行
        try:
            logger.info("准备调用_run_agent_with_interrupt: question=%s", content)
            result = await _run_agent_with_interrupt(
                question=content,
                capture_steps=True,
                minimal=False,
                session_id=session_id,
            )
            logger.info("完成调用_run_agent_with_interrupt, result=%s", result)
        except Exception as e:
            logger.error("调用_run_agent_with_interrupt失败: %s", e)
            logger.exception("调用_run_agent_with_interrupt详细错误:")

    try:
        logger.info("开始订阅Redis消息: session_id=%s", session_id)
        # 保持循环以维持监控器活跃状态
        async for msg in RedisBus.subscribe_messages(session_id):
            logger.info("收到Redis消息: %s", msg)
            try:
                await _handle_message(msg)
            except asyncio.CancelledError:
                logger.info("消息处理被取消")
                raise
            except Exception as ie:
                logger.error("处理会话收件箱消息失败: %r", ie)
                logger.exception("处理会话收件箱消息详细错误:")
                await asyncio.sleep(0.1)
    except asyncio.CancelledError:
        logger.info("会话收件箱监控器被取消: %s", session_id)
    except Exception as e:
        logger.error("会话收件箱监控器异常 session_id=%s err=%r", session_id, e)
        logger.exception("会话收件箱监控器详细异常:")
    finally:
        try:
            await RedisBus.unregister_session(session_id)
            logger.info("成功注销会话: %s", session_id)
        except Exception as e:
            logger.warning("注销会话失败: %s, error: %s", session_id, e)


async def register_session_inbox_monitor():
    """注册会话收件箱监控器"""
    manager = await get_monitor_manager()
    
    session_inbox_monitor_def = Monitor(
        name="session_inbox",
        description="会话收件箱监控器。",
        parameters={
            "session_id": "会话ID"
        },
        start_func=session_inbox_monitor
    )
    
    manager.register_monitor(session_inbox_monitor_def)
    logger.info("注册session_inbox监控器完成")
    return session_inbox_monitor_def