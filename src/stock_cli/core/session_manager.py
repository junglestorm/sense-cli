"""会话管理器，支持根据配置自动启动触发器"""

import asyncio
import logging
from typing import Dict, Any, Optional, List

from .session import SessionManager as BaseSessionManager
from ..triggers import TRIGGER_REGISTRY

logger = logging.getLogger(__name__)


class SessionManager:
    """扩展的会话管理器，支持触发器模式"""
    
    def __init__(self):
        self._base_manager = BaseSessionManager()
        self._trigger_tasks: Dict[str, asyncio.Task] = {}
        
    def get_session(self, session_id: str) -> Any:
        """获取会话实例"""
        return self._base_manager.get_session(session_id)
    
    
    async def start_session_triggers(self, session_id: str, session_config: Dict[str, Any]):
        """根据会话配置启动触发器"""
        if session_config.get("mode") != "trigger":
            return
            
        triggers = session_config.get("triggers", [])
        if not triggers:
            logger.info(f"会话 {session_id} 没有配置触发器")
            return
            
        for trigger_config in triggers:
            if not trigger_config.get("enabled", False):
                continue
                
            trigger_type = trigger_config.get("type")
            if trigger_type not in TRIGGER_REGISTRY:
                logger.warning(f"未知的触发器类型: {trigger_type}")
                continue
                
            # 启动触发器任务
            task = asyncio.create_task(
                self._run_trigger(session_id, trigger_type, trigger_config)
            )
            self._trigger_tasks[f"{session_id}_{trigger_type}"] = task
            logger.info(f"会话 {session_id} 的触发器 {trigger_type} 已启动")
    
    async def _run_trigger(self, session_id: str, trigger_type: str, trigger_config: Dict[str, Any]):
        """运行单个触发器"""
        try:
            # 通过注册机制获取并运行触发器
            trigger_func = TRIGGER_REGISTRY.get(trigger_type)
            if trigger_func:
                await trigger_func(session_id, trigger_config)
            else:
                logger.warning(f"触发器 {trigger_type} 没有注册触发器函数")
        except Exception as e:
            logger.error(f"运行触发器 {trigger_type} 时出错: {e}")
    
    async def stop_session_triggers(self, session_id: str):
        """停止会话的所有触发器"""
        tasks_to_cancel = []
        for key, task in list(self._trigger_tasks.items()):
            if key.startswith(f"{session_id}_"):
                tasks_to_cancel.append(task)
                del self._trigger_tasks[key]
                
        for task in tasks_to_cancel:
            task.cancel()
            
        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
        logger.info(f"会话 {session_id} 的所有触发器已停止")