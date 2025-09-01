"""事件系统

用于ReAct执行过程中的事件发射和处理
提供与旧版progress_cb接口的兼容适配器
"""

import time
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Callable, Awaitable, Optional


class ReActEventType(Enum):
    """ReAct事件类型"""

    ITERATION_START = "iteration_start"
    THOUGHT = "thinking"
    ACTION = "action"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
    STREAM_CHUNK = "stream_chunk"
    THOUGHT_HEADER = "thinking_header"
    ACTION_HEADER = "action_header"
    MONITOR_HEADER = "monitor_header"


@dataclass
class ReActEvent:
    """ReAct事件"""

    type: ReActEventType
    data: Dict[str, Any]
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class EventEmitter:
    """事件发射器"""

    def __init__(self):
        self._handlers = {}

    def on(self, event_type: ReActEventType, handler):
        """注册事件处理器"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    async def emit(self, event: ReActEvent):
        """发射事件"""
        handlers = self._handlers.get(event.type, [])
        for handler in handlers:
            await handler(event)


class ProgressCallbackAdapter:
    """将事件转换为旧的progress_cb格式的适配器"""

    def __init__(self, progress_cb: Optional[Callable[[str], Awaitable[None]]]):
        self.progress_cb = progress_cb
        self.emitter = EventEmitter()
        self._setup_adapters()

    def _setup_adapters(self):
        """设置事件到回调的适配"""
        if not self.progress_cb:
            return

        # 注册事件适配器
        self.emitter.on(ReActEventType.THOUGHT_HEADER, self._adapt_thought_header)
        self.emitter.on(ReActEventType.ACTION_HEADER, self._adapt_action_header)
        self.emitter.on(ReActEventType.MONITOR_HEADER, self._adapt_monitor_header)
        self.emitter.on(ReActEventType.FINAL_ANSWER, self._adapt_final_answer)
        self.emitter.on(ReActEventType.STREAM_CHUNK, self._adapt_stream_chunk)

    async def _adapt_thought_header(self, event: ReActEvent):
        """适配思考头部事件"""
        await self.progress_cb("[ThinkingHeader]")

    async def _adapt_action_header(self, event: ReActEvent):
        """适配动作头部事件"""
        await self.progress_cb("[ActionHeader]")

    async def _adapt_monitor_header(self, event: ReActEvent):
        """适配监控器头部事件"""
        await self.progress_cb("[MonitorHeader]")

    async def _adapt_final_answer(self, event: ReActEvent):
        """适配最终答案事件"""
        await self.progress_cb("[FinalAnswerHeader]")

    async def _adapt_stream_chunk(self, event: ReActEvent):
        """适配流式输出事件"""
        chunk_type = event.data.get("type", "default")
        content = event.data.get("content", "")

        if chunk_type == "thinking":
            await self.progress_cb(f"[StreamThinking]{content}")
        elif chunk_type == "action":
            await self.progress_cb(f"[StreamAction]{content}")
        elif chunk_type == "observation":
            # 工具返回结果
            await self.progress_cb(f"[StreamObservation]{content}")
        elif chunk_type == "final_answer":
            await self.progress_cb(f"[StreamFinalAnswer]{content}")
        elif chunk_type == "final_answer_end":
            await self.progress_cb("[FinalAnswerEnd]")
        elif chunk_type == "monitor":
            await self.progress_cb(f"[StreamMonitor]{content}")
        else:
            await self.progress_cb(content)

    async def emit(self, event: ReActEvent):
        """发射事件（适配器接口）"""
        await self.emitter.emit(event)
