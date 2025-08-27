from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from ..core.session import Session
from ..core.llm_provider import LLMProvider
from ..core.prompt_loader import PromptBuilder
from ..core.types import AgentConfig, Task, TaskStatus,Context,Scratchpad
from ..tools.mcp_server_manager import MCPServerManager
from .events import ReActEvent, ReActEventType, ProgressCallbackAdapter
from .xml_filter import XMLStreamFilter
from ..utils.redis_bus import RedisBus

logger = logging.getLogger(__name__)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

class AgentKernel:
    def __init__(
        self,
        llm_provider: LLMProvider,
        session: Session,
        prompt_builder: PromptBuilder,
        config: AgentConfig,
    ):
        self.llm_provider = llm_provider
        self.session = session
        self.prompt_builder = prompt_builder
        self.config = config
        self._last_action_payload: str = ""
        self._last_final_answer: str = ""
        self._last_communication_payload: str = ""
        self.scratchpad: list = []
        self._scratchpad_history: list = []  # 用于保留历史scratchpad内容
        self._current_request_token_usage: dict = {}  # 当前请求的token使用量
 
    # ---------------- 公共入口 ----------------
    async def run(
        self,
        description: str,
        progress_cb: Optional[Callable[[str], Awaitable[None] | None]] = None,
        record_user_question: bool = True,
    ) -> Any:
        """
        简化入口：按描述执行一个任务
        - 统一由 Kernel 内部创建 Task
        - 可选将描述写入 qa_history（遵循 Unix：单一职责，对外提供最小接口）
        """
        if record_user_question:
            try:
                # 注入当前时间到 context
                import datetime
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.session.context["current_time"] = {
                    "role": "system",
                    "content": f"[当前时间] {now_str},对任何时间相关的问题,一律使用这个时间为准,此为当前task开始时间"
                }
                self.session.append_qa({"role": "user", "content": description})
            except Exception:
                pass
        task = self.session.create_task(description=description)
        return await self.execute_task(task, progress_cb=progress_cb)
 
    async def execute_task(
        self,
        task: Task,
        progress_cb: Optional[Callable[[str], Awaitable[None] | None]] = None,
    ) -> Any:
        logger.debug(f"执行任务: {task.description}")
        task.status = TaskStatus.RUNNING
        total_start = time.time()
        total_timeout = min(task.timeout or self.config.timeout, self.config.timeout)
        event_adapter = ProgressCallbackAdapter(progress_cb)
        
        # 保留最近3次的scratchpad历史
        if len(self._scratchpad_history) > 3:
            self._scratchpad_history.pop(0)
        
        # 将当前scratchpad内容保存到历史中（如果有内容）
        if self.scratchpad:
            self._scratchpad_history.append(self.scratchpad.copy())
        
        # 重置当前scratchpad，但保留历史供参考
        self.scratchpad: list = []  # 直接用 List[Message]

        # 在进入循环前构建 ReAct 提示词（包含 available_tools / scratchpad / qa_history）
        try:
            try:
                mgr = await MCPServerManager.get_instance()
                all_tools = await mgr.list_tools()
                
                # 根据角色配置过滤可用工具
                tools_for_prompt = self._filter_tools_by_role(all_tools)
            except Exception:
                tools_for_prompt = []

            ctx = self.session.context
            memory_ctx_content = ""
            try:
                if isinstance(ctx.get("memory_context"), dict):
                    memory_ctx_content = ctx["memory_context"].get("content", "")
            except Exception:
                pass

            qa_history = ctx.get("qa_history", [])

            # 动态获取在线会话列表，注入到 ReAct 提示中供模型感知与选择
            try:
                active_sessions = await RedisBus.list_active_sessions()
                # 过滤掉当前会话自身，避免自引用
                active_sessions = [sid for sid in active_sessions if sid != self.session.session_id]
            except Exception:
                active_sessions = []

            # 合并scratchpad历史到当前scratchpad中
            combined_scratchpad = []
            for historical_scratchpad in self._scratchpad_history:
                combined_scratchpad.extend(historical_scratchpad)
            combined_scratchpad.extend(self.scratchpad)
            
            react_prompt_text = self.prompt_builder.build_react_prompt(
                current_task=task.description,
                scratchpad=combined_scratchpad,
                available_tools=tools_for_prompt,
                memory_context=memory_ctx_content,
                conversation_history=qa_history,
                active_sessions=active_sessions,
            )
            # 将完整的 ReAct 提示作为 system 消息注入，驱动模型严格输出<thinking>/<action>/<final_answer>
            self.session.context["react_prompt"] = {"role": "system", "content": react_prompt_text}
        except Exception as e:
            logger.warning("构建 ReAct 提示失败，将使用默认上下文: %s", e)

        try:
            result = await self._execute_react_loop(
                task,
                event_adapter=event_adapter,
                total_start=total_start,
                total_timeout=total_timeout,
            )
            task.result = result
            task.status = TaskStatus.COMPLETED
            return result
        except Exception as e:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            logger.exception("任务执行失败")
            raise

    
    

    # ---------------- ReAct 主循环 ----------------
    async def _execute_react_loop(
        self,
        task: Task,
        event_adapter: ProgressCallbackAdapter,
        total_start: float,
        total_timeout: float,
    ) -> str:
        """
        逻辑：
        1. 流式获取模型输出，XML 解析器捕获 <action> 或 <final_answer>
        2. 若得到 <final_answer> -> 返回
        3. 若得到 <action> JSON -> 调用工具，把结果注入对话后进入下一迭代
        4. 若什么都没有 -> 视为直接回答（fallback）返回
        不再存在“同一迭代第二次调用”与复杂兜底。
        """
        logger.info("开始精简循环: %s", task.description[:80])
        iteration = 0
        max_iter = task.max_iterations

        while iteration < max_iter:
            if time.time() - total_start > total_timeout:
                logger.warning("达到总体超时限制，提前终止")
                break
            iteration += 1
            task.current_iteration = iteration
            await event_adapter.emit(ReActEvent(ReActEventType.ITERATION_START, {"iteration": iteration}))

            # 每轮开始时重置上次流标记，避免旧的 action/final 干扰本轮分支判断
            await self._reset_stream_markers()

            # 动态注入在线会话信息供模型感知
            try:
                active_sessions = await RedisBus.list_active_sessions()
                if isinstance(active_sessions, list):
                    # 过滤掉当前会话自身，避免自引用
                    other_sessions = [sid for sid in active_sessions if sid != self.session.session_id]
                    bullet = "\n".join([f"- {sid}" for sid in other_sessions]) if other_sessions else "无其他在线会话"
                    # 1. 作为独立 system message 注入
                    self.session.context["active_sessions"] = {
                        "role": "system",
                        "content": "[可对话会话列表]\n" + bullet + "\n请优先参考本列表与其他会话通信。"
                    }
            except Exception:
                # 忽略注入失败，保证主流程
                pass

            # 单次模型调用
            
            # 由session负责构建LLM输入消息
            messages, token_info = self.session.build_llm_messages(
                task=task,
                scratchpad=self.scratchpad,
            )
            # 存储当前请求的token信息
            self._current_request_token_usage = token_info
            
            # 等待模型响应
            response_text = await self._stream_llm_call(
                messages,
                self.config.llm_max_tokens,
                total_timeout - (time.time() - total_start), 
                event_adapter
            )
            # 单一回调处理所有情况（case风格）
            result = await self._handle_react_iteration_case(event_adapter,  response_text)
            if result is not None:
                return result

        logger.warning("达到最大迭代次数 %d 未完成", max_iter)
        return "任务结束: 达到迭代/时间限制。"

    async def _handle_react_iteration_case(
        self,
        event_adapter: ProgressCallbackAdapter,
        response_text: str
    ) -> Optional[str]:
        """case风格处理 final_answer、action、fallback 三种情况"""
        action_name, action_args = self._parse_action_json(self._last_action_payload)
        comm_target, comm_message = self._parse_communication_json(self._last_communication_payload)
        cases = {
            "final_answer": bool(self._last_final_answer),
            "action": bool(action_name and self._last_action_payload),
            "communication": bool(comm_target and self._last_communication_payload),
            "fallback": not self._last_final_answer and not action_name and not comm_target,
        }
        # case: final_answer
        if cases["final_answer"]:
            final_answer = self._last_final_answer.strip()
            
            #最终回答无需添加进scratchpad中，因为循环即将结束
            self.session.append_qa({"role": "assistant", "content": final_answer})
    
            await event_adapter.emit(
                ReActEvent(ReActEventType.STREAM_CHUNK, {"content": "", "type": "final_answer_end"})
            )
            return final_answer

        # case: action
        if cases["action"]:
            await self._run_tool_and_record(action_name, action_args, event_adapter)
            
            return None  # 继续下一轮

        # case: communication
        if cases["communication"]:
            # 记录通信调用
            comm_json = json.dumps({"communication": {"target": comm_target, "message": comm_message}}, ensure_ascii=False)
            self.session.append_qa({"role": "assistant", "content": comm_json})
            try:
                subs = await RedisBus.publish_message(self.session.session_id, comm_target, comm_message)
                observation = f"Communication sent to '{comm_target}'. subscribers={subs}"
            except Exception as e:
                observation = f"ERROR: communication failed: {e}"

            # 注入到 scratchpad，供下一轮分析
            self.scratchpad.append({
                "role": "assistant",
                "content": f"Communication: {comm_json}"
            })
            self.scratchpad.append({
                "role": "user",
                "content": f"Observation: {observation}"
            })

            await event_adapter.emit(
                ReActEvent(ReActEventType.STREAM_CHUNK, {"content": observation, "type": "observation"})
            )
            return None  # 继续下一轮

        # case: fallback
        if cases["fallback"]:
            fallback_raw = self._extract_fallback_final(response_text)
            self.scratchpad.append({"role": "assistant", "content": fallback_raw})
            self.scratchpad.append({
                "role": "user",
                "content": (
                    "上一次输出未提供 <action>、<communication> 或 <final_answer>。请严格按照系统提示中的XML输出格式，仅输出 <thinking> + (<action> / <communication> 或 <final_answer>)，不要输出其它说明文字。"
                )
            })
            return None

        return None

    # ---------------- 消息与模型调用 ----------------

    # _build_messages 已移除，由 session/build_messages_for_llm 负责

    async def _stream_llm_call(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        timeout: float,
        event_adapter: ProgressCallbackAdapter,
    ) -> str:
        xml_filter = XMLStreamFilter()
        collected: List[str] = []
        thinking_buf: List[str] = []
        action_buf: List[str] = []
        communication_buf: List[str] = []
        final_buf: List[str] = []
        thought_shown = action_shown = final_shown = False
        action_end_detected = False
        communication_end_detected = False
        final_answer_end_detected = False
        chunks_after_end = 0
        # 保留context tokens信息，只重置completion相关的token计数
        if self._current_request_token_usage:
            self._current_request_token_usage.update({
                "completion_tokens": 0,
                "total_tokens": self._current_request_token_usage.get("context_tokens", 0)
            })

        try:
            async for chunk in self.llm_provider.generate_stream(
                messages, max_tokens=max_tokens, timeout=int(timeout), session=self.session
            ):
                if not chunk:
                    continue
                collected.append(chunk)
                filtered, section = xml_filter.process_chunk(chunk)

                # header events
                if section == "thinking" and not thought_shown:
                    await event_adapter.emit(ReActEvent(ReActEventType.THOUGHT_HEADER, {}))
                    thought_shown = True
                elif section == "action" and not action_shown:
                    await event_adapter.emit(ReActEvent(ReActEventType.ACTION_HEADER, {}))
                    action_shown = True
                elif section == "final_answer" and not final_shown:
                    await event_adapter.emit(ReActEvent(ReActEventType.FINAL_ANSWER, {"content": ""}))
                    final_shown = True

                # buffer collect
                if section == "action" and filtered:
                    action_buf.append(filtered)
                elif section == "communication" and filtered:
                    communication_buf.append(filtered)
                elif section == "final_answer" and filtered:
                    final_buf.append(filtered)
                elif section == "action_end":
                    self._last_action_payload = "".join(action_buf).strip()
                    # 不立即break，等待可能的usage信息
                    action_end_detected = True
                elif section == "communication_end":
                    self._last_communication_payload = "".join(communication_buf).strip()
                    # 不立即break，等待可能的usage信息
                    communication_end_detected = True
                elif section == "final_answer_end":
                    # 捕获最终答案，但不立即break，等待可能的usage信息
                    self._last_final_answer = "".join(final_buf).strip()
                    final_answer_end_detected = True

                if filtered and filtered.strip():
                    await event_adapter.emit(
                        ReActEvent(
                            ReActEventType.STREAM_CHUNK,
                            {"content": filtered, "type": section or "default"},
                        )
                    )
                
                # 检查是否需要break（在检测到结束标签后，再处理几个chunk以确保usage信息被处理）
                if action_end_detected or communication_end_detected or final_answer_end_detected:
                    chunks_after_end += 1
                    # 在处理结束标签后，再处理3个chunk以确保usage信息被捕获
                    if chunks_after_end >= 3:
                        break

            # 收尾兜底（未遇到 *_end 标签）
            if action_buf and not self._last_action_payload:
                self._last_action_payload = "".join(action_buf).strip()
            if communication_buf and not self._last_communication_payload:
                self._last_communication_payload = "".join(communication_buf).strip()
            if final_buf and not self._last_final_answer:
                self._last_final_answer = "".join(final_buf).strip()
            return "".join(collected)
        except Exception as e:  # noqa: BLE001
            logger.warning("流式处理异常: %s", e)
            # 抛出异常而不是回退到非流式调用
            raise


    # ---------------- 工具执行与辅助 ----------------
    async def _run_tool_and_record(
        self,
        action: str,
        arguments: Dict[str, Any],
        event_adapter: ProgressCallbackAdapter,
    ) -> str:
        call_json = json.dumps({"tool": action, "arguments": arguments}, ensure_ascii=False)
        # 记录工具调用的简要信息到全局qa_history（可追溯）
        self.session.append_qa({"role": "assistant", "content": call_json})
        try:
            mgr = await MCPServerManager.get_instance()
            raw_result = await mgr.call_tool(action, arguments or {})
            observation = self._format_observation(raw_result)

            # 将本轮 action 与 observation 以“对话消息”的形式注入 scratchpad，供下一轮 LLM 分析
            # - assistant: 代表上一轮模型的动作
            # - user: 代表环境返回的观察结果
            self.scratchpad.append({
                "role": "assistant",
                "content": f"Action: {call_json}"
            })
            self.scratchpad.append({
                "role": "user",
                "content": f"Observation: {observation}"
            })

            # 将 observation 通过事件流输出到终端以便可视化
            await event_adapter.emit(
                ReActEvent(ReActEventType.STREAM_CHUNK, {"content": observation, "type": "observation"})
            )
            return observation
        except Exception as e:  # noqa: BLE001
            err = f"ERROR: {e}"

            # 注入失败情况下同样保持“动作→观察”的对话形态，确保下一轮有足够上下文自行决策
            self.scratchpad.append({
                "role": "assistant",
                "content": f"Action: {call_json}"
            })
            self.scratchpad.append({
                "role": "user",
                "content": f"Observation: {err}"
            })

            await event_adapter.emit(
                ReActEvent(ReActEventType.STREAM_CHUNK, {"content": err, "type": "observation"})
            )
            # 记录失败上下文（便于排查）
            try:
                logger.warning("工具调用失败 action=%s args=%s err=%r", action, arguments, e)
            except Exception:
                pass
            self.session.append_qa({
                "role": "assistant",
                "content": "工具调用失败。请只在确有必要时再尝试一次修正，否则直接输出 <final_answer> 总结。",
            })
            return err

    def _format_observation(self, raw_result: Any) -> str:
        """
        将工具返回规范化为可读文本，优先提取 MCP ToolResponse.content[*].text；
        否则当为 dict 时输出 JSON；最后退化为 str(raw_result)。统一做长度截断。
        """
        try:
            if hasattr(raw_result, "content"):
                texts: List[str] = []
                for item in getattr(raw_result, "content") or []:
                    txt = None
                    if hasattr(item, "text"):
                        txt = item.text
                    elif isinstance(item, dict):
                        txt = item.get("text")
                    if txt:
                        texts.append(str(txt))
                obs = "\n".join(texts) if texts else str(raw_result)
            elif isinstance(raw_result, dict):
                obs = json.dumps(raw_result, ensure_ascii=False)
            else:
                obs = str(raw_result)
        except Exception as e:
            obs = f"ERROR: 规范化工具返回失败: {e!r}"
        obs = (obs or "").strip()
        if len(obs) > 16000:
            obs = obs[:16000]
        return obs

    async def _reset_stream_markers(self):
        self._last_action_payload = ""
        self._last_communication_payload = ""
        self._last_final_answer = ""

    def _parse_action_json(self, raw: str) -> Tuple[str, Dict[str, Any]]:
        if not raw:
            return "", {}
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            obj = json.loads(cleaned)
            if isinstance(obj, dict) and "tool" in obj:
                args = obj.get("arguments")
                if isinstance(args, dict):
                    return str(obj["tool"]), args
        except Exception:
            return "", {}

    def _parse_communication_json(self, raw: str) -> Tuple[str, str]:
        if not raw:
            return "", ""
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            obj = json.loads(cleaned)
            if isinstance(obj, dict):
                target = str(obj.get("target") or "").strip()
                message = str(obj.get("message") or "").strip()
                if target and message:
                    return target, message
        except Exception:
            return "", ""
        return "", ""

    def _extract_fallback_final(self, response: str) -> str:
        # 去掉 action/communication json 片段，只返回可读文本
        if self._last_action_payload:
            try:
                response = response.replace(self._last_action_payload, "")
            except Exception:  # noqa: BLE001
                pass
        if self._last_communication_payload:
            try:
                response = response.replace(self._last_communication_payload, "")
            except Exception:  # noqa: BLE001
                pass
        return response.strip() or "任务完成"

    def _filter_tools_by_role(self, all_tools: List[Any]) -> List[Any]:
        """根据角色配置过滤可用工具 - 现在通过提示词控制，不再硬编码过滤"""
        # 不再进行硬编码过滤，全部工具都可用
        # 工具使用权限通过角色提示词来控制
        return all_tools