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
    """记忆管理器"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.vector_store = None
        self.structured_db_path = config.get(
            "structured_db_path", "data/db/structured_memory.sqlite"
        )

        # 初始化结构化数据库
        self._init_structured_db()

        # 初始化向量数据库
        if CHROMADB_AVAILABLE:
            self._init_vector_store()

    def _init_structured_db(self):
        """初始化结构化数据库"""
        os.makedirs(os.path.dirname(self.structured_db_path), exist_ok=True)

        with sqlite3.connect(self.structured_db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS watchlist (
                    symbol TEXT PRIMARY KEY,
                    name TEXT,
                    market TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    priority INTEGER DEFAULT 2
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS analysis_history (
                    id TEXT PRIMARY KEY,
                    task_id TEXT,
                    task_description TEXT,
                    analysis_result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.commit()

        logger.info(f"结构化数据库已初始化: {self.structured_db_path}")

    def _init_vector_store(self):
        """初始化向量数据库"""
        if not CHROMADB_AVAILABLE:
            return

        try:
            vector_store_path = self.config.get("vector_store_path", "data/db/vector_store")
            os.makedirs(vector_store_path, exist_ok=True)

            client = chromadb.PersistentClient(
                path=vector_store_path,
                settings=Settings(allow_reset=True, anonymized_telemetry=False),
            )

            collection_name = self.config.get("collection_name", "stock_analysis_memory")
            self.vector_store = client.get_or_create_collection(
                name=collection_name, metadata={"hnsw:space": "cosine"}
            )

            logger.info(f"向量数据库已初始化: {vector_store_path}")

        except Exception as e:
            logger.error(f"初始化向量数据库失败: {str(e)}")
            self.vector_store = None

    async def store_long_term_memory(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """存储长期记忆"""
        if not self.vector_store:
            logger.warning("向量数据库不可用，无法存储长期记忆")
            return ""

        try:
            memory_entry = MemoryEntry(content=content, metadata=metadata or {})

            # 存储到向量数据库
            self.vector_store.add(
                documents=[memory_entry.content],
                ids=[memory_entry.id],
                metadatas=[memory_entry.metadata],
            )

            logger.info(f"已存储长期记忆: {memory_entry.id}")
            return memory_entry.id

        except Exception as e:
            logger.error(f"存储长期记忆失败: {str(e)}")
            return ""

    async def retrieve_relevant_memories(
        self, query: str, max_results: int = 10
    ) -> List[MemoryEntry]:
        """检索相关记忆"""
        if not self.vector_store:
            return []

        try:
            results = self.vector_store.query(query_texts=[query], n_results=max_results)

            memories = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    memory = MemoryEntry(
                        id=results["ids"][0][i] if results["ids"] else "",
                        content=doc,
                        metadata=results["metadatas"][0][i] if results["metadatas"] else {},
                        relevance_score=(
                            1 - results["distances"][0][i] if results["distances"] else 0
                        ),
                    )
                    memories.append(memory)

            logger.info(f"检索到 {len(memories)} 条相关记忆")
            return memories

        except Exception as e:
            logger.error(f"检索记忆失败: {str(e)}")
            return []

    def store_analysis_result(self, task: Task, result: str):
        """存储分析结果到结构化数据库"""
        try:
            with sqlite3.connect(self.structured_db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO analysis_history 
                    (id, task_id, task_description, analysis_result)
                    VALUES (?, ?, ?, ?)
                """,
                    (task.id, task.id, task.description, result),
                )
                conn.commit()

            logger.info(f"已存储分析结果: {task.id}")

        except Exception as e:
            logger.error(f"存储分析结果失败: {str(e)}")

    def get_watchlist(self) -> List[Dict[str, Any]]:
        """获取关注列表"""
        try:
            with sqlite3.connect(self.structured_db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT symbol, name, market, priority 
                    FROM watchlist 
                    ORDER BY priority DESC, added_at DESC
                """
                )
                return [
                    {"symbol": row[0], "name": row[1], "market": row[2], "priority": row[3]}
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            logger.error(f"获取关注列表失败: {str(e)}")
            return []

    def add_to_watchlist(self, symbol: str, name: str, market: str, priority: int = 2):
        """添加到关注列表"""
        try:
            with sqlite3.connect(self.structured_db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO watchlist 
                    (symbol, name, market, priority, added_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                    (symbol, name, market, priority),
                )
                conn.commit()

            logger.info(f"已添加到关注列表: {symbol}")

        except Exception as e:
            logger.error(f"添加到关注列表失败: {str(e)}")

    def remove_from_watchlist(self, symbol: str):
        """从关注列表移除"""
        try:
            with sqlite3.connect(self.structured_db_path) as conn:
                conn.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
                conn.commit()

            logger.info(f"已从关注列表移除: {symbol}")

        except Exception as e:
            logger.error(f"从关注列表移除失败: {str(e)}")

    def get_user_preference(self, key: str, default: Any = None) -> Any:
        """获取用户偏好设置"""
        try:
            with sqlite3.connect(self.structured_db_path) as conn:
                cursor = conn.execute("SELECT value FROM user_preferences WHERE key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return default

        except Exception as e:
            logger.error(f"获取用户偏好失败: {str(e)}")
            return default

    def set_user_preference(self, key: str, value: Any):
        """设置用户偏好"""
        try:
            with sqlite3.connect(self.structured_db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_preferences 
                    (key, value, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """,
                    (key, json.dumps(value)),
                )
                conn.commit()

            logger.info(f"已更新用户偏好: {key}")

        except Exception as e:
            logger.error(f"设置用户偏好失败: {str(e)}")


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
                    f"相关记忆 {i+1}: {memory.content}"
                    for i, memory in enumerate(relevant_memories)
                ]
                context["memory_context"] = "\n\n".join(memory_texts)

        # 获取用户偏好（不覆盖已有的偏好设置）
        if "user_preferences" not in context or not context["user_preferences"]:
            context["user_preferences"] = {
                "watchlist": self.memory_manager.get_watchlist(),
                "analysis_style": self.memory_manager.get_user_preference(
                    "analysis_style", "comprehensive"
                ),
                "risk_tolerance": self.memory_manager.get_user_preference("risk_tolerance", "moderate"),
            }
        
        # 确保 memory_context 存在
        if "memory_context" not in context:
            context["memory_context"] = ""

        return context

    def truncate_context(self, text: str) -> str:
        """截断过长的上下文"""
        if len(text) <= self.max_context_length:
            return text

        # 简单截断策略：保留开头和结尾
        half_length = self.max_context_length // 2 - 50
        truncated = text[:half_length] + "\n\n... [内容已截断] ...\n\n" + text[-half_length:]

        logger.info(f"上下文已截断: {len(text)} -> {len(truncated)} 字符")
        return truncated
