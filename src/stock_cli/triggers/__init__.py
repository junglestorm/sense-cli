"""触发器注册机制"""

import logging
import importlib
import pkgutil
import sys
from pathlib import Path
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


def discover_triggers() -> Dict[str, Any]:
    """
    发现并返回所有可用的触发器函数
    
    Returns:
        Dict[str, Any]: 触发器名称到触发器函数的映射
    """
    # 确保所有触发器模块都已加载
    auto_discover()
    
    # 直接返回注册表中的触发器函数
    return TRIGGER_REGISTRY.copy()


def auto_discover() -> None:
    """
    自动发现并导入当前包下的所有触发器模块，以触发 @register 装饰器完成注册。
    通过动态导入实现入口与具体触发器实现解耦。
    """
    pkg_dir = Path(__file__).parent
    for mod in pkgutil.iter_modules([str(pkg_dir)]):
        name = mod.name
        if name.startswith("_") or name == "__init__":
            continue
        full_name = f"{__name__}.{name}"
        if full_name in sys.modules:
            # 已加载
            continue
        try:
            importlib.import_module(full_name)
            logger.debug(f"触发器模块已加载: {full_name}")
        except Exception as e:
            logger.error(f"加载触发器模块失败: {full_name}: {e}")


# 为兼容性提供别名
try:
    from ..core.config_resolver import load_triggers_config as load_trigger_config
except ImportError:
    # 在独立测试时提供空函数
    def load_trigger_config(*args, **kwargs):
        return {}

__all__ = [
    "TRIGGER_REGISTRY",
    "register",
    "get",
    "list_triggers",
    "discover_triggers",
    "auto_discover",
    "load_trigger_config",
]