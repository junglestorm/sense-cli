"""触发器注册机制"""

import logging
from typing import Callable, Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# 触发器注册表：type -> trigger_function
TRIGGER_REGISTRY: Dict[str, Callable] = {}


def register(trigger_type: str):
    """注册触发器函数"""
    def decorator(func):
        TRIGGER_REGISTRY[trigger_type] = func
        logger.debug(f"触发器已注册: {trigger_type}")
        return func
    return decorator


def get(trigger_type: str) -> Optional[Callable]:
    """获取触发器函数"""
    return TRIGGER_REGISTRY.get(trigger_type)


def list_triggers() -> List[str]:
    """列出所有已注册的触发器类型"""
    return list(TRIGGER_REGISTRY.keys())


__all__ = [
    "TRIGGER_REGISTRY",
    "register",
    "get",
    "list_triggers",
]