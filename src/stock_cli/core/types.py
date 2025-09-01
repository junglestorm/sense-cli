"""
核心数据结构和类型定义
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict, Union

from pydantic import BaseModel, Field



# 标准化历史条目类型
from typing import Literal

class QAItem(TypedDict):
    role: Literal['user', 'event', 'agent', 'tool', 'system']
    content: str
    # 可扩展更多字段，如 timestamp, tool_name, etc.

# OpenAI标准消息格式
class Message(TypedDict):
    role: Literal['system', 'user', 'assistant', 'tool']
    content: str

class Context(TypedDict):
    """
    符合OpenAI标准的上下文结构，用于构建传递给LLM的消息
    所有字段都会被转换为标准的Message格式
    """
   
    # 系统级提示信息 - 将转换为 {"role": "system", "content": system_prompt}
    system_prompt: Message
    
    # 工具使用策略 - 将转换为 {"role": "system", "content": tool_policy}
    tool_policy: Message
    
    # 可用工具列表 - 将转换为 {"role": "system", "content": 工具描述文本}
    available_tools: Message
    
    # 记忆/外部知识上下文 - 将转换为 {"role": "system", "content": memory_context}
    memory_context: Message
    
    # ReAct提示词 - 将转换为 {"role": "system", "content": react_prompt}
    react_prompt: Message

    # 任务与最终结果历史记录（符合OpenAI消息格式）,内部message的role只能为user或者assistant
    qa_history: List[Message]
    
    # 当前task描述
    task_description: Message


class Scratchpad(TypedDict, total=False):
    """ReAct单步执行记录"""

    # 模型返回的思考、工具调用、返回值轨迹,role为assistant、tool
    trace: List[Message]
    
    

 
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


class Task(BaseModel):
    """任务对象接口"""

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

    # 移除context字段，Task不再直接管理context
    # context: TaskContext = Field(default_factory=dict)
    # scratchpad移到运行时处理，不在Task对象中持久化存储

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

