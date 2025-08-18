"""触发器注册与发现（Triggers Registry）

职责：
- 提供一个轻量级注册表，将 trigger 类型字符串映射到具体的构建函数（builder）
- 每个 builder 接收来自配置文件的 spec(dict)，返回三元组 (role, content, task_template)
- 由命令层的 TriggerEngine 负责循环与调度与内核调用，builder 仅专注于“如何构造本次触发的任务内容”

扩展方式：
- 在 src/stock_cli/triggers/ 下新增模块（如 ask_time.py）
- 在模块内实现一个 builder 函数，并通过 @register("type_name") 装饰器注册
- 在触发配置（config/triggers.yaml）中使用同名 type 即可启用
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple, List, Awaitable

# (role, content, task_template)
BuildTaskResult = Tuple[str, str, Optional[str]]
TriggerFunc = Callable[[dict], BuildTaskResult]

TRIGGER_REGISTRY: Dict[str, TriggerFunc] = {}


def register(name: str) -> Callable[[TriggerFunc], TriggerFunc]:
    """
    装饰器：将一个 builder 函数注册到注册表。
    用法：
        @register("ask_time")
        def build(spec: dict) -> BuildTaskResult: ...
    """
    def _decorator(func: TriggerFunc) -> TriggerFunc:
        TRIGGER_REGISTRY[name] = func
        return func
    return _decorator


def get(name: str) -> Optional[TriggerFunc]:
    """获取已注册的 trigger builder；未注册返回 None。"""
    return TRIGGER_REGISTRY.get(name)


def list_triggers() -> List[str]:
    """列出所有已注册的 trigger 类型名称。"""
    return sorted(TRIGGER_REGISTRY.keys())




__all__ = [
    "BuildTaskResult",
    "TriggerFunc",
    "TRIGGER_REGISTRY",
    "register",
    "get",
    "list_triggers",
]