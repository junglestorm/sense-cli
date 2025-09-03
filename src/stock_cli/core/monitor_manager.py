"""监控器管理器

负责管理监控器的注册、启动和生命周期管理
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Callable, Any, Awaitable
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Monitor:
    """监控器定义"""
    name: str
    description: str
    parameters: Dict[str, str]  # 参数名: 参数描述
    start_func: Callable[[Dict[str, Any]], Awaitable[None]]


class MonitorManager:
    """监控器管理器"""
    
    _instance: Optional['MonitorManager'] = None
    
    def __init__(self):
        self._monitors: Dict[str, Monitor] = {}
        self._active_monitors: Dict[str, asyncio.Task] = {}
        
    @classmethod
    async def get_instance(cls) -> 'MonitorManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register_monitor(self, monitor: Monitor):
        """注册监控器"""
        if monitor.name in self._monitors:
            logger.warning("监控器 %s 已存在，将被覆盖", monitor.name)
        self._monitors[monitor.name] = monitor
        logger.info("注册监控器: %s", monitor.name)
    
    def list_monitors(self) -> List[Dict[str, Any]]:
        """列出所有可用监控器"""
        result = []
        for monitor in self._monitors.values():
            result.append({
                "name": monitor.name,
                "description": monitor.description,
                "parameters": monitor.parameters,
            })
        return result
    
    def list_active_monitors(self) -> List[Dict[str, Any]]:
        """列出所有活跃监控器"""
        return [
            {
                "id": monitor_id,
                "name": task.get_name().replace("monitor_", ""),
                "running": not task.done(),
            }
            for monitor_id, task in self._active_monitors.items()
        ]
    
    async def start_monitor(self, monitor_name: str, arguments: Dict[str, Any]) -> str:
        """启动监控器"""
        if monitor_name not in self._monitors:
            available = list(self._monitors.keys())
            raise ValueError(f"未知的监控器: {monitor_name}，可用监控器: {available}")
        
        monitor = self._monitors[monitor_name]
        monitor_id = f"{monitor_name}_{int(time.time())}"
        
        # 启动监控器任务
        task = asyncio.create_task(
            self._run_monitor(monitor, arguments, monitor_id),
            name=f"monitor_{monitor_id}"
        )
        
        self._active_monitors[monitor_id] = task
        logger.info("启动监控器: %s (ID: %s)", monitor_name, monitor_id)
        
        return monitor_id
    
    async def _run_monitor(self, monitor: Monitor, arguments: Dict[str, Any], monitor_id: str):
        """运行监控器任务"""
        try:
            await monitor.start_func(arguments)
        except asyncio.CancelledError:
            logger.info("监控器 %s 被取消", monitor_id)
        except Exception as e:
            logger.error("监控器 %s 运行失败: %s", monitor_id, e)
            logger.exception("监控器运行详细错误:")
        finally:
            # 从活跃监控器中移除
            if monitor_id in self._active_monitors:
                del self._active_monitors[monitor_id]
    
    async def stop_monitor(self, monitor_id: str):
        """停止监控器"""
        if monitor_id not in self._active_monitors:
            raise ValueError(f"监控器 {monitor_id} 未运行")
        
        task = self._active_monitors[monitor_id]
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        
            if monitor_id in self._active_monitors:
                del self._active_monitors[monitor_id]
        logger.info("停止监控器: %s", monitor_id)
    
    async def stop_all_monitors(self):
        """停止所有监控器"""
        if not self._active_monitors:
            return
        
        tasks = []
        monitor_ids = list(self._active_monitors.keys())
        
        for monitor_id in monitor_ids:
            task = asyncio.create_task(self.stop_monitor(monitor_id))
            tasks.append(task)  
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("停止监控器 %s 失败: %s", monitor_ids[i], result)
            else:
                logger.info("停止监控器 %s 成功", monitor_ids[i])


# 添加全局函数以便导入
async def get_monitor_manager() -> MonitorManager:
    """获取监控器管理器实例"""
    return await MonitorManager.get_instance()