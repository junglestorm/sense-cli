"""
任务管理器 - 处理任务的生命周期管理
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..core.context import MemoryManager
from ..core.types import Task, TaskPriority, TaskStatus, TriggerEvent

logger = logging.getLogger(__name__)


class TaskManager:
    """任务管理器"""

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.active_tasks: Dict[str, Task] = {}
        self.task_queue: List[Task] = []
        self.completed_tasks: List[Task] = []
        self.max_concurrent_tasks = 3

    def create_task(
        self,
        description: str,
        priority: TaskPriority = TaskPriority.NORMAL,
        context: Dict[str, Any] = None,
    ) -> Task:
        """创建新任务"""
        task = Task(description=description, priority=priority, context=context or {})

        logger.info(f"创建任务: {task.id} - {description[:50]}...")
        return task

    def add_task(self, task: Task):
        """添加任务到队列"""
        # 按优先级插入到合适位置
        inserted = False
        for i, existing_task in enumerate(self.task_queue):
            if task.priority.value > existing_task.priority.value:
                self.task_queue.insert(i, task)
                inserted = True
                break

        if not inserted:
            self.task_queue.append(task)

        logger.info(f"任务已加入队列: {task.id} (优先级: {task.priority.name})")

    def get_next_task(self) -> Optional[Task]:
        """获取下一个待执行任务"""
        if not self.task_queue:
            return None

        # 检查并发限制
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            return None

        task = self.task_queue.pop(0)
        self.active_tasks[task.id] = task
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()

        logger.info(f"开始执行任务: {task.id}")
        return task

    def complete_task(self, task: Task, result: Any = None, error: str = None):
        """标记任务完成"""
        task.completed_at = datetime.now()
        task.result = result
        task.error_message = error

        if error:
            task.status = TaskStatus.FAILED
            logger.error(f"任务执行失败: {task.id} - {error}")
        else:
            task.status = TaskStatus.COMPLETED
            logger.info(f"任务执行完成: {task.id}")

        # 从活动任务中移除
        if task.id in self.active_tasks:
            del self.active_tasks[task.id]

        # 加入完成列表
        self.completed_tasks.append(task)

        # 存储分析结果到记忆
        if result and not error:
            self.memory_manager.store_analysis_result(task, str(result))

    def cancel_task(self, task_id: str):
        """取消任务"""
        # 从队列中移除
        self.task_queue = [t for t in self.task_queue if t.id != task_id]

        # 从活动任务中移除
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()
            del self.active_tasks[task_id]
            self.completed_tasks.append(task)
            logger.info(f"任务已取消: {task_id}")

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """获取任务状态"""
        # 检查活动任务
        if task_id in self.active_tasks:
            return self.active_tasks[task_id].status

        # 检查队列
        for task in self.task_queue:
            if task.id == task_id:
                return task.status

        # 检查完成列表
        for task in self.completed_tasks:
            if task.id == task_id:
                return task.status

        return None

    def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态"""
        return {
            "queued_tasks": len(self.task_queue),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "queue": [
                {
                    "id": task.id,
                    "description": task.description[:50],
                    "priority": task.priority.name,
                    "created_at": task.created_at.isoformat(),
                }
                for task in self.task_queue
            ],
            "active": [
                {
                    "id": task.id,
                    "description": task.description[:50],
                    "started_at": task.started_at.isoformat()
                    if task.started_at
                    else None,
                    "current_iteration": task.current_iteration,
                }
                for task in self.active_tasks.values()
            ],
        }

    def cleanup_old_tasks(self, days: int = 7):
        """清理旧任务"""
        cutoff_date = datetime.now() - timedelta(days=days)

        # 清理完成任务中的旧任务
        old_count = len(self.completed_tasks)
        self.completed_tasks = [
            task
            for task in self.completed_tasks
            if task.completed_at and task.completed_at > cutoff_date
        ]
        new_count = len(self.completed_tasks)

        if old_count > new_count:
            logger.info(f"清理了 {old_count - new_count} 个旧任务")

    async def process_task_queue(self):
        """处理任务队列的主循环"""
        logger.info("任务队列处理器启动")

        while True:
            try:
                # 获取下一个任务
                task = self.get_next_task()

                if task:
                    # 这里会被Agent的kernel接管具体执行
                    logger.info(f"任务 {task.id} 等待Agent处理")
                else:
                    # 没有任务时短暂等待
                    await asyncio.sleep(1)

                # 定期清理
                if len(self.completed_tasks) > 100:
                    self.cleanup_old_tasks()

            except Exception as e:
                logger.error(f"任务队列处理错误: {e}")
                await asyncio.sleep(5)


class TriggerManager:
    """触发器管理器"""

    def __init__(self, task_manager: TaskManager):
        self.task_manager = task_manager
        self.triggers: List[TriggerEvent] = []
        self.running = False

    def add_trigger(self, trigger: TriggerEvent):
        """添加触发器"""
        self.triggers.append(trigger)
        logger.info(f"添加触发器: {trigger.name}")

    def remove_trigger(self, trigger_name: str):
        """移除触发器"""
        self.triggers = [t for t in self.triggers if t.name != trigger_name]
        logger.info(f"移除触发器: {trigger_name}")

    async def start_monitoring(self):
        """开始监控触发器"""
        self.running = True
        logger.info("触发器监控启动")

        while self.running:
            try:
                for trigger in self.triggers:
                    if trigger.enabled and await self._check_trigger(trigger):
                        # 创建触发的任务
                        task = self.task_manager.create_task(
                            description=trigger.task_template,
                            priority=trigger.priority,
                            context={
                                "triggered_by": trigger.name,
                                "trigger_type": trigger.type,
                            },
                        )
                        self.task_manager.add_task(task)

                        # 更新最后触发时间
                        trigger.last_triggered = datetime.now()

                        logger.info(f"触发器 {trigger.name} 创建了任务: {task.id}")

                await asyncio.sleep(60)  # 每分钟检查一次

            except Exception as e:
                logger.error(f"触发器监控错误: {e}")
                await asyncio.sleep(30)

    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        logger.info("触发器监控停止")

    async def _check_trigger(self, trigger: TriggerEvent) -> bool:
        """检查触发器是否应该触发"""
        try:
            if trigger.type == "time":
                return await self._check_time_trigger(trigger)
            elif trigger.type == "event":
                return await self._check_event_trigger(trigger)
            else:
                logger.warning(f"未知触发器类型: {trigger.type}")
                return False
        except Exception as e:
            logger.error(f"检查触发器失败 {trigger.name}: {e}")
            return False

    async def _check_time_trigger(self, trigger: TriggerEvent) -> bool:
        """检查时间触发器"""
        # 简化实现：检查是否到了触发时间
        # 实际项目中需要更完整的cron表达式解析
        condition = trigger.condition
        cron_expr = condition.get("cron")

        if not cron_expr:
            return False

        # 这里需要实现cron表达式解析
        # 暂时简化：如果上次触发超过1小时，就可以再次触发
        if trigger.last_triggered:
            time_diff = datetime.now() - trigger.last_triggered
            return time_diff.total_seconds() > 3600  # 1小时

        return True  # 首次触发

    async def _check_event_trigger(self, trigger: TriggerEvent) -> bool:
        """检查事件触发器"""
        # 简化实现：事件触发器需要更复杂的逻辑
        # 比如监控股价变化、新闻事件等
        # 这里只是占位符
        return False
