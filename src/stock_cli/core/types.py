"""
核心数据结构和类型定义
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """任务优先级"""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    """任务对象"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 执行相关
    max_iterations: int = 20
    timeout: int = 300  # 秒
    current_iteration: int = 0

    # 上下文
    context: Dict[str, Any] = Field(default_factory=dict)
    scratchpad: List[str] = Field(default_factory=list)  # ReAct轨迹

    # 结果
    result: Optional[Any] = None
    error_message: Optional[str] = None


class LLMProviderConfig(BaseModel):
    """LLM提供商配置"""

    provider_name: str
    api_key: str
    base_url: str
    model: str
    max_tokens: int = 1024
    temperature: float = 0.1
    timeout: int = 120
    fallback_model: Optional[str] = None


class ReActStep(BaseModel):
    """ReAct单步执行记录"""

    step: int
    thinking: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)


class MemoryEntry(BaseModel):
    """记忆条目"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    relevance_score: Optional[float] = None


class AgentConfig(BaseModel):
    """Agent配置"""

    # max_iterations 字段已移除，统一由 Task 控制
    timeout: int = 300
    context_window: int = 8192
    max_memory_results: int = 10
    summary_threshold: int = 2000

    # LLM配置
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    provider_name: str = "openai"

    # 工具配置
    tool_timeout: int = 30
    max_tool_retries: int = 3


class TriggerEvent(BaseModel):
    """触发事件"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: str  # "time" or "event"
    condition: Dict[str, Any]
    task_template: str
    priority: TaskPriority = TaskPriority.NORMAL
    enabled: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    last_triggered: Optional[datetime] = None


class StockInfo(BaseModel):
    """股票信息"""

    symbol: str
    name: str
    market: str  # A股, US, HK等
    current_price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    last_updated: Optional[datetime] = None


class MarketData(BaseModel):
    """市场数据"""

    symbol: str
    timestamp: datetime
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    adj_close: Optional[float] = None


class NewsItem(BaseModel):
    """新闻条目"""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    url: Optional[str] = None
    source: str
    published_at: datetime
    symbols_mentioned: List[str] = Field(default_factory=list)
    sentiment_score: Optional[float] = None  # -1到1之间
