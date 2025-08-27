from typing import Dict, List, Any, Optional
import json
import logging
from pathlib import Path
import os

from .types import Task, Context, Message,Scratchpad

logger = logging.getLogger(__name__)

TOOL_POLICY = (
    "Tool use policy:\n"
    "1. 在 <action> 中输出严格 JSON: {\"tool\": \"name\", \"arguments\": {...}} (双引号, 无多余文本)。\n"
    "2. 每轮至多一个 <action>；如信息足够可直接输出 <final_answer>。\n"
    "3. 避免重复调用同一工具+参数；若已有结果请直接利用生成答案。\n"
    "4. 通常不应超过 3 次工具调用，尽早给出 <final_answer>。\n"
    "5. 工具失败可做一次合理修正；再失败或无必要继续请直接 <final_answer> 解释。\n"
)


class Session:
    def __init__(self, session_id: str, role_config: Optional[Dict[str, Any]] = None, role_name: Optional[str] = None):
        self.session_id = session_id
        self._context: Context = self._default_context()
        # session 级别的上下文持久化文件（每个 session 一个文件）
        self._session_file = Path("logs") / "sessions" / f"{self.session_id}.json"
        try:
            self._session_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        
        # 角色配置（先初始化属性，再加载磁盘上下文）
        self.role_name = role_name
        self.role_config: Optional[Dict[str, Any]] = None
        
        # 若存在历史上下文文件，则加载以延续会话
        self._load_context_from_disk()
        
        # 触发器引用表（运行期使用，不参与持久化）
        self.triggers: Dict[str, Any] = {}
        
        # 注入角色配置（支持旧格式和新格式）
        if role_config:
            self._inject_role_config(role_config)
        elif role_name:
            self._load_role_config(role_name)

    def _default_context(self) -> Context:
        return {
            "system_prompt": {"role": "system", "content": ""},
            "tool_policy": {"role": "system", "content": TOOL_POLICY},
            "available_tools": {"role": "system", "content": ""},
            "memory_context": {"role": "system", "content": ""},
            "current_time": {"role": "system", "content": ""},
            "user_preferences": {"role": "system", "content": json.dumps({
                "watchlist": [],
                "analysis_style": "comprehensive",
                "risk_tolerance": "moderate",
            })},
            "react_prompt": {"role": "system", "content": ""},
            "active_sessions": {"role": "system", "content": "[可对话会话列表]\n无其他在线会话"},
            "qa_history": [],
            "token_usage": {"role": "system", "content": json.dumps({
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "last_updated": ""
            })},
        }


    @property
    def context(self) -> Context:
        return self._context

    @context.setter
    def context(self, ctx: Context):
        self._context = ctx

    def get_context(self) -> Context:
        return self._context

    def set_context(self, ctx: Context):
        # 确保所有字段都为 Message 类型，qa_history 为 List[Message]
        new_ctx = self._default_context()
        for k in new_ctx:
            if k == "qa_history":
                if k in ctx and isinstance(ctx[k], list):
                    # 只保留 role 为 user/assistant 的消息
                    new_ctx[k] = [m for m in ctx[k] if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content")]
            elif k in ctx and isinstance(ctx[k], dict) and "role" in ctx[k] and "content" in ctx[k]:
                new_ctx[k] = ctx[k]
        self._context = new_ctx

    def _has_role_config(self) -> bool:
        """检查是否有有效的角色配置"""
        return hasattr(self, 'role_config') and self.role_config is not None

    def _inject_role_config(self, role_config: Dict[str, Any]):
        """注入角色配置到系统提示词"""
        try:
            if role_config.get("system_prompt"):
                self._context["system_prompt"]["content"] = role_config["system_prompt"]
            if role_config.get("persona"):
                # 将角色描述添加到系统提示词
                persona_text = f"\n\n角色设定: {role_config['persona']}"
                self._context["system_prompt"]["content"] += persona_text
            # 保存角色配置供后续使用
            self.role_config = role_config
        except Exception as e:
            logger.warning("注入角色配置失败 session_id=%s err=%r", self.session_id, e)
    
    def _load_role_config(self, role_name: str):
        """从角色管理器加载角色配置"""
        try:
            from .role_manager import get_role_manager
            role_manager = get_role_manager()
            role_config = role_manager.get_role(role_name)
            
            if role_config:
                # 注入系统提示词
                self._context["system_prompt"]["content"] = role_config.system_prompt
                # 保存角色配置
                from .role_manager import get_role_manager
                role_manager = get_role_manager()
                self.role_config = role_manager.role_config_to_dict(role_config)
                logger.info(f"成功加载角色配置: {role_name}")
            else:
                logger.warning(f"角色配置不存在: {role_name}")
        except Exception as e:
            logger.warning(f"加载角色配置失败 session_id={self.session_id} role={role_name} err={e}")


    def build_llm_messages(self, task: Task, scratchpad: list = None) -> List[Message]:
        """
        组装 LLM 输入消息：context（全局）+ scratchpad（本 task）+ 当前任务描述。
        所有消息都符合OpenAI标准格式
        这个方法在task循环中构建，而非开始新task时构建
        """
        messages: List[Message] = []
        ctx = self._context

        # 1. system_prompt
        if ctx.get("system_prompt"):
            messages.append(ctx["system_prompt"])

        # 2. tool_policy
        if ctx.get("tool_policy"):
            messages.append(ctx["tool_policy"])

        # 3. available_tools
        if ctx.get("available_tools"):
            messages.append(ctx["available_tools"])
 
        # 4. memory_context
        if ctx.get("memory_context"):
            messages.append(ctx["memory_context"])

        # 4.1 current_time
        if ctx.get("current_time"):
            messages.append(ctx["current_time"])
 
        # 4.5 active_sessions（动态发现的在线会话列表，供模型感知通信对象）
        if ctx.get("active_sessions"):
            messages.append(ctx["active_sessions"])
 
        # 5. react_prompt
        if ctx.get("react_prompt"):
            messages.append(ctx["react_prompt"])
 
        # 6. qa_history
        qa_history = ctx.get("qa_history", [])
        if isinstance(qa_history, list):
            messages.extend([m for m in qa_history if isinstance(m, dict) and m.get("role") in ("user", "assistant") and m.get("content")])
 
        # 7. 当前任务描述
        if task and getattr(task, "description", None):
            messages.append({"role": "user", "content": task.description})
 
        # 8. scratchpad（task链路）
        if scratchpad:
            messages.extend(scratchpad)

        return messages






    def clear_context(self):
        self._context = self._default_context()
        # 清空后立即落盘，确保磁盘与内存一致
        self._save_context_to_disk()


    def append_qa(self, qa_item: Message):
        # 只允许 user/assistant
        if qa_item.get("role") in ("user", "assistant") and qa_item.get("content"):
            self._context["qa_history"].append(qa_item)
            # 写入后保存整个 session 上下文，形成“以 session 为单位”的记录
            self._save_context_to_disk()

    def append_event(self, role: str, content: str):
        """
        附加触发事件到会话历史：
        - 按触发来源自定义 role（如 'system_scheduler'、'crawler_event' 等）
        - 仅参与持久化展示；当前不会被纳入 LLM 对话上下文（build_llm_messages 仅带入 user/assistant）
        """
        try:
            if not content:
                return
            self._context["qa_history"].append({"role": role, "content": content})
            self._save_context_to_disk()
        except Exception as e:
            logger.warning("追加事件到会话失败 session_id=%s role=%s err=%r", self.session_id, role, e)


    def summary_qa_history(self):
        #TODO 
        pass

    def create_task(self, description: str, **kwargs) -> Task:
        return Task(description=description, **kwargs)
        



    # ---------------- 持久化（以 session 为单位） ----------------
    def _save_context_to_disk(self) -> None:
        try:
            data = {
                "session_id": self.session_id,
                "context": self._context,
            }
            # 保存角色配置信息
            if self._has_role_config():
                data["role_config"] = self.role_config
            if hasattr(self, 'role_name') and self.role_name:
                data["role_name"] = self.role_name
                
            with open(self._session_file, "w", encoding="utf-8") as f:
                f.write(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.warning("保存会话上下文失败 session_id=%s err=%r", self.session_id, e)

    def _load_context_from_disk(self) -> None:
        try:
            if self._session_file.exists():
                with open(self._session_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # 仅当结构合理时替换当前上下文
                if isinstance(loaded, dict) and "context" in loaded and isinstance(loaded["context"], dict):
                    # 做一次 set_context 规范化
                    self.set_context(loaded["context"])  # type: ignore[arg-type]
                    
                    # 加载保存的角色配置信息
                    if "role_config" in loaded and isinstance(loaded["role_config"], dict):
                        self.role_config = loaded["role_config"]
                    if "role_name" in loaded and isinstance(loaded["role_name"], str):
                        self.role_name = loaded["role_name"]
                    
                    # 如果会话有角色配置，重新注入角色配置
                    if self._has_role_config():
                        self._inject_role_config(self.role_config)
                    elif hasattr(self, 'role_name') and self.role_name:
                        self._load_role_config(self.role_name)
        except Exception as e:
            logger.warning("加载会话上下文失败 session_id=%s err=%r", self.session_id, e)


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def get_session(self, session_id: str, role_config: Optional[Dict[str, Any]] = None, role_name: Optional[str] = None) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id, role_config, role_name)
        elif role_config or role_name:
            # 如果会话已存在但有新的角色配置，重新注入
            if role_config:
                self._sessions[session_id]._inject_role_config(role_config)
            elif role_name:
                self._sessions[session_id]._load_role_config(role_name)
        return self._sessions[session_id]

    def remove_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]

    def all_sessions(self) -> List[str]:
        return list(self._sessions.keys())

    # -------- 扩展：会话发现与注册（基于轻量消息总线） --------
    async def register_session_to_redis(self, session_id: str) -> None:
        """将会话注册到在线集合，便于其他会话发现"""
        try:
            from ..utils.redis_bus import RedisBus
            await RedisBus.register_session(session_id)
        except Exception:
            # 注册失败不影响主流程
            pass

    async def unregister_session_from_redis(self, session_id: str) -> None:
        """从在线集合注销会话"""
        try:
            from ..utils.redis_bus import RedisBus
            await RedisBus.unregister_session(session_id)
        except Exception:
            pass

    async def get_active_sessions_from_redis(self) -> List[str]:
        """获取所有在线会话ID列表"""
        try:
            from ..utils.redis_bus import RedisBus
            return await RedisBus.list_active_sessions()
        except Exception:
            return []

