from typing import Dict, List, Any
import json
import logging

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
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._context: Context = self._default_context()

    def _default_context(self) -> Context:
        return {
            "system_prompt": {"role": "system", "content": ""},
            "tool_policy": {"role": "system", "content": TOOL_POLICY},
            "available_tools": {"role": "system", "content": ""},
            "memory_context": {"role": "system", "content": ""},
            "user_preferences": {"role": "system", "content": json.dumps({
                "watchlist": [],
                "analysis_style": "comprehensive",
                "risk_tolerance": "moderate",
            })},
            "react_prompt": {"role": "system", "content": ""},
            "qa_history": [],
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


    def append_qa(self, qa_item: Message):
        # 只允许 user/assistant
        if qa_item.get("role") in ("user", "assistant") and qa_item.get("content"):
            self._context["qa_history"].append(qa_item)


    def summary_qa_history(self):
        #TODO 
        pass

    def create_task(self, description: str, **kwargs) -> Task:
        return Task(description=description, **kwargs)
        



class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def get_session(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id)
        return self._sessions[session_id]

    def remove_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]

    def all_sessions(self) -> List[str]:
        return list(self._sessions.keys())
