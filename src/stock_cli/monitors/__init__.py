"""监控器模块初始化"""

from .session_inbox import register_session_inbox_monitor
from .loop_timer import register_loop_timer_monitor
from .fixed_time_timer import register_fixed_time_timer_monitor

async def register_all_monitors():
    """注册所有监控器"""
    # 注册会话收件箱监控器
    await register_session_inbox_monitor()
    
    # 注册循环定时器监控器
    await register_loop_timer_monitor()
    
    # 注册固定时间定时器监控器
    await register_fixed_time_timer_monitor()