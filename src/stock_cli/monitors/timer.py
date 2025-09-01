"""定时器监控器

实现定时提醒功能的监控器
"""

import asyncio
import time
import logging
from typing import Dict, Any
from ..core.monitor_manager import Monitor, get_monitor_manager

logger = logging.getLogger(__name__)

async def timer_monitor(arguments: Dict[str, Any]):
    """定时器监控器实现
    
    Args:
        arguments: 包含 interval(秒), message(提醒消息), 和 target_session(目标会话)
    """
    interval = arguments.get("interval", 60)
    message = arguments.get("message", "时间到！")
    target_session = arguments.get("target_session", "default")
    
    logger.info("启动定时器监控器: interval=%s, message=%s, target_session=%s", interval, message, target_session)
    
    if not isinstance(interval, (int, float)) or interval <= 0:
        raise ValueError("interval 必须是正数")
    
    # 使用智能定时问题模板
    reminder_message = f"这是一个定时提醒：{message}"
    
    count = 0
    while True:
        count += 1
        logger.info("定时器第%d次触发", count)
        await asyncio.sleep(interval)
        logger.info("定时器休眠结束，准备发送消息")
        
        # 发送提醒消息到Redis总线，触发完整的session task循环
        try:
            from ..utils.redis_bus import RedisBus
            # 确保Redis连接已建立
            await RedisBus._ensure_client()
            # 使用特殊的sender标识，让session知道这是监控器触发的消息
            # 发送到启动监控器的目标会话
            logger.info("定时器准备发送消息: %s -> %s: %s", "monitor_system", target_session, reminder_message)
            subs = await RedisBus.publish_message(
                "monitor_system",  # 发送者标识（不是当前会话，避免被过滤）
                target_session,    # 接收者（启动监控器的会话）
                reminder_message   # 提醒消息（优先使用原始用户消息），会触发完整的task循环
            )
            logger.info("定时器成功发送消息: %s -> %s: %s (订阅者数量: %d)", "monitor_system", target_session, reminder_message, subs)
            
            # 如果没有订阅者，记录警告信息
            if subs <= 0:
                logger.warning("没有订阅者接收消息，消息可能丢失: %s -> %s: %s", 
                              "monitor_system", target_session, reminder_message)
        except Exception as e:
            # 如果Redis不可用，直接输出到控制台并记录详细日志
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] ⏰ {reminder_message}")
            logger.warning("定时器Redis发送失败: %s", e)
            logger.exception("Redis连接详细错误信息:")

async def register_timer_monitor():
    """注册定时器监控器"""
    manager = await get_monitor_manager()
    
    timer_monitor_def = Monitor(
        name="timer",
        description="定时提醒监控器，定期发送提醒消息",
        parameters={
            "interval": "提醒间隔（秒）",
            "message": "提醒消息内容",
            "target_session": "目标会话ID"
        },
        start_func=timer_monitor
    )
    
    manager.register_monitor(timer_monitor_def)
    logger.info("注册timer监控器完成")
    return timer_monitor_def