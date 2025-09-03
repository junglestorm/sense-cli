TOOL_POLICY = (
    "Tool use policy:\n"
    "1. 在 <action> 中输出严格 JSON: {\"tool\": \"name\", \"arguments\": {...}} (双引号, 无多余文本)。\n"
    "2. 每轮至多一个 <action>；如信息足够可直接输出 <final_answer>。\n"
    "3. 避免重复调用同一工具+参数；若已有结果请直接利用生成答案。\n"
    "4. 通常不应超过 3 次工具调用，尽早给出 <final_answer>。\n"
    "5. 工具失败可做一次合理修正；再失败或无必要继续请直接 <final_answer> 解释。\n"
)
"""
上下文和记忆管理模块
"""

import json
import logging
import os
import sqlite3
from typing import Any, Dict, List

from .types import MemoryEntry, Task

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB不可用，长期记忆功能将被禁用")


class MemoryManager:
    """记忆管理器(后期实现)"""

    pass


class ContextManager:
    """上下文管理器"""

    def __init__(self, memory_manager: MemoryManager, max_context_length: int = 8192):
        self.memory_manager = memory_manager
        self.max_context_length = max_context_length

    async def build_context_for_task(self, task: Task) -> Dict[str, Any]:
        """为任务构建上下文"""
        # 从任务现有的上下文开始（这样可以保留持久上下文，如对话历史）
        context = task.context.copy() if task.context else {}

        # 添加任务执行所需的基本信息（只在不存在时添加）
        if "task" not in context:
            context["task"] = task
        if "scratchpad" not in context:
            context["scratchpad"] = task.scratchpad

        # 检索相关的长期记忆
        if task.description:
            relevant_memories = await self.memory_manager.retrieve_relevant_memories(
                task.description, max_results=5
            )

            if relevant_memories:
                memory_texts = [
                    f"相关记忆 {i + 1}: {memory.content}"
                    for i, memory in enumerate(relevant_memories)
                ]
                context["memory_context"] = "\n\n".join(memory_texts)

        # 使用RAG检索相关文档
        try:
            from .rag import get_rag_instance
            rag = await get_rag_instance()
            if rag and task.description:
                rag_documents = await rag.retrieve(task.description, top_k=3)
                if rag_documents:
                    rag_texts = [
                        f"相关文档 {i + 1}: {doc.content}"
                        for i, doc in enumerate(rag_documents)
                    ]
                    rag_context = "\n\n".join(rag_texts)
                    # 将RAG上下文与现有记忆上下文合并
                    if "memory_context" in context and context["memory_context"]:
                        context["memory_context"] += "\n\n" + rag_context
                    else:
                        context["memory_context"] = rag_context
        except Exception as e:
            logger.warning(f"RAG检索失败: {str(e)}")

        # 获取用户偏好（不覆盖已有的偏好设置）
        if "user_preferences" not in context or not context["user_preferences"]:
            context["user_preferences"] = {
                "watchlist": self.memory_manager.get_watchlist(),
                "analysis_style": self.memory_manager.get_user_preference(
                    "analysis_style", "comprehensive"
                ),
                "risk_tolerance": self.memory_manager.get_user_preference(
                    "risk_tolerance", "moderate"
                ),
            }

        # 确保 memory_context 存在
        if "memory_context" not in context:
            context["memory_context"] = ""

        return context