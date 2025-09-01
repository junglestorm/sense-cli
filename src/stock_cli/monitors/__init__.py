"""监控器包初始化

自动发现和注册所有监控器
"""

import importlib
import pkgutil
import asyncio
from typing import Dict, Callable, Any, Awaitable
import logging

logger = logging.getLogger(__name__)

# 存储所有监控器注册函数
_monitor_registrars: Dict[str, Callable[[], Awaitable[Any]]] = {}

def auto_discover():
    """自动发现监控器注册函数"""
    package = __name__
    prefix = package + "."
    
    for _, module_name, _ in pkgutil.iter_modules(__path__, prefix):
        try:
            # 特殊处理timer和session_inbox模块
            if module_name.endswith('.timer'):
                # 直接导入timer模块并注册
                from . import timer
                _monitor_registrars['timer'] = timer.register_timer_monitor
                logger.debug("发现监控器注册函数: timer")
                continue
                
            if module_name.endswith('.session_inbox'):
                # 直接导入session_inbox模块并注册
                from . import session_inbox
                _monitor_registrars['session_inbox'] = session_inbox.register_session_inbox_monitor
                logger.debug("发现监控器注册函数: session_inbox")
                continue
                
            module = importlib.import_module(module_name)
            # 查找模块中的 register_* 函数
            for attr_name in dir(module):
                if attr_name.startswith('register_') and callable(getattr(module, attr_name)):
                    registrar_name = attr_name.replace('register_', '')
                    _monitor_registrars[registrar_name] = getattr(module, attr_name)
                    logger.debug("发现监控器注册函数: %s", registrar_name)
        except ImportError as e:
            logger.warning("导入监控器模块 %s 失败: %s", module_name, e)
            logger.exception("详细错误信息:")

async def register_all_monitors():
    """注册所有监控器"""
    auto_discover()
    
    # 确保监控器管理器已初始化
    from ..core.monitor_manager import get_monitor_manager
    await get_monitor_manager()
    
    registered_count = 0
    for registrar_name, registrar_func in _monitor_registrars.items():
        try:
            await registrar_func()
            logger.info("成功注册监控器: %s", registrar_name)
            registered_count += 1
        except Exception as e:
            logger.error("注册监控器 %s 失败: %s", registrar_name, e)
            logger.exception("详细错误信息:")
    
    logger.info("总共注册了 %d 个监控器", registered_count)

def get_monitor_registrar(monitor_type: str) -> Callable[[], Awaitable[Any]]:
    """获取指定类型的监控器注册函数"""
    return _monitor_registrars.get(monitor_type)

def list_available_monitors() -> list:
    """列出所有可用的监控器类型"""
    return list(_monitor_registrars.keys())