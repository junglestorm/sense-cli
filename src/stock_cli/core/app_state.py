"""应用状态管理器"""

import asyncio
from typing import Dict, Any, Optional


class ApplicationState:
    """应用状态管理器，用于封装原本分散的全局状态"""
    
    def __init__(self):
        self._current_task: Optional[asyncio.Task] = None
        self._interrupt_requested: bool = False
        self._persistent_context: Dict[str, Any] = {}
        
    @property
    def current_task(self) -> Optional[asyncio.Task]:
        return self._current_task
        
    @current_task.setter
    def current_task(self, task: Optional[asyncio.Task]):
        self._current_task = task
        
    @property
    def interrupt_requested(self) -> bool:
        return self._interrupt_requested
        
    @interrupt_requested.setter
    def interrupt_requested(self, value: bool):
        self._interrupt_requested = value
        
    @property
    def persistent_context(self) -> Dict[str, Any]:
        return self._persistent_context
        
    def reset_interrupt(self):
        """重置中断标志"""
        self._interrupt_requested = False


# 全局应用状态实例
app_state = ApplicationState()