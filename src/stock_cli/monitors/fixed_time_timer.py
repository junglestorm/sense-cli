"""固定时间定时器监控器

实现在特定时间点提醒功能的监控器
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from ..core.monitor_manager import Monitor, get_monitor_manager

logger = logging.getLogger(__name__)

async def fixed_time_timer_monitor(arguments: Dict[str, Any]):
    """固定时间定时器监控器实现
    
    Args:
        arguments: 包含 time(提醒时间，格式HH:MM), message(提醒消息), 和 target_session(目标会话)
    """
    remind_time = arguments.get("time", "09:00")
    message = arguments.get("message", "时间到！")
    target_session = arguments.get("target_session", "default")
    
    logger.info("启动固定时间定时器监控器: time=%s, message=%s, target_session=%s", remind_time, message, target_session)
    
    # 验证时间格式
    try:
        hour, minute = map(int, remind_time.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("时间超出有效范围")
    except ValueError as e:
        raise ValueError(f"时间格式错误，应为HH:MM格式: {e}")
    
    # 使用智能定时问题模板
    reminder_message = f"这是固定时间提醒：{message}"
    
    count = 0
    while True:
        count += 1
        logger.info("固定时间定时器第%d次检查", count)
        
        # 计算下次触发时间
        now = datetime.now()
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # 如果今天的时间已经过了，设置为明天的时间
        if next_run <= now:
            next_run += timedelta(days=1)
        
        # 计算等待时间
        wait_seconds = (next_run - now).total_seconds()
        logger.info("固定时间定时器下次触发时间: %s (等待%s秒)", next_run, wait_seconds)
        
        # 等待到指定时间
        await asyncio.sleep(wait_seconds)
        logger.info("固定时间定时器触发，准备发送消息")
        
        # 发送提醒消息到Redis总线，触发完整的session task循环
        try:
            from ..utils.redis_bus import RedisBus
            # 确保Redis连接已建立
            await RedisBus._ensure_client()
            # 发送到启动监控器的目标会话
            logger.info("固定时间定时器准备发送消息: %s -> %s: %s", "monitor_system", target_session, reminder_message)
            subs = await RedisBus.publish_message(
                "monitor_system",     # 发送者标识
                target_session,       # 接收者（启动监控器的会话）
                reminder_message,     # 提醒消息，会触发完整的task循环
                {}                    # 传递额外参数
            )
            logger.info("固定时间定时器成功发送消息: %s -> %s: %s (订阅者数量: %d)", "monitor_system", target_session, reminder_message, subs)
            
            # 如果没有订阅者，记录警告信息
            if subs <= 0:
                logger.warning("没有订阅者接收消息，消息可能丢失: %s -> %s: %s", 
                              "monitor_system", target_session, reminder_message)
        except Exception as e:
            # 如果Redis不可用，直接输出到控制台并记录详细日志
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] ⏰ {reminder_message}")
            logger.warning("固定时间定时器Redis发送失败: %s", e)
            logger.exception("Redis连接详细错误信息:")

async def register_fixed_time_timer_monitor():
    """注册固定时间定时器监控器"""
    manager = await get_monitor_manager()
    
    fixed_time_timer_monitor_def = Monitor(
        name="fixed_time_timer",
        description="固定时间提醒监控器，在指定时间点发送提醒消息",
        parameters={
            "time": "提醒时间（HH:MM格式）",
            "message": "提醒消息内容",
            "target_session": "目标会话ID"
        },
        start_func=fixed_time_timer_monitor
    )
    
    manager.register_monitor(fixed_time_timer_monitor_def)
    logger.info("注册fixed_time_timer监控器完成")
    return fixed_time_timer_monitor_def