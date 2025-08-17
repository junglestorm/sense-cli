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
        self.scratchpad: list = []

    # ---------------- 公共入口 ----------------
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
        self.scratchpad: list = []  # 直接用 List[Message]

        # 在进入循环前构建 ReAct 提示词（包含 available_tools / scratchpad / qa_history）
        try:
            try:
                mgr = await MCPServerManager.get_instance()
                tools_for_prompt = await mgr.list_tools()
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

            react_prompt_text = self.prompt_builder.build_react_prompt(
                current_task=task.description,
                scratchpad=self.scratchpad,
                available_tools=tools_for_prompt,
                memory_context=memory_ctx_content,
                conversation_history=qa_history,
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
            self._write_qa_history_to_file(task)
            return result
        except Exception as e:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            logger.exception("任务执行失败")
            self._write_qa_history_to_file(task)
            raise

    def _write_qa_history_to_file(self, task: Task):
        """将qa_history写入文件"""
        try:
            qa_history = self.session.context.get("qa_history", [])
            if not qa_history:
                return
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            file_name = f"qa_history_{task.id or timestamp}.json"
            file_path = os.path.join("logs", file_name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(json.dumps(qa_history, ensure_ascii=False, indent=2))
            logger.info(f"qa_history已写入文件: {file_path}")
        except Exception as e:
            logger.error(f"写入qa_history失败: {e}")
    
    

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

            # 单次模型调用
            
            # 由session负责构建LLM输入消息
            messages = self.session.build_llm_messages(
                task=task,
                scratchpad=self.scratchpad,
            )
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
        cases = {
            "final_answer": bool(self._last_final_answer),
            "action": bool(action_name and self._last_action_payload),
            "fallback": not self._last_final_answer and not action_name,
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

        # case: fallback
        if cases["fallback"]:
            fallback_raw = self._extract_fallback_final(response_text)
            self.scratchpad.append({"role": "assistant", "content": fallback_raw})
            self.scratchpad.append({
                "role": "user",
                "content": (
                    "上一次输出未提供 <action> 或 <final_answer>。请严格按照系统提示中的XML输出格式，仅输出 <thinking> + (<action> 或 <final_answer>)，不要输出其它说明文字。"
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
        final_buf: List[str] = []
        thought_shown = action_shown = final_shown = False

        try:
            async for chunk in self.llm_provider.generate_stream(
                messages, max_tokens=max_tokens, timeout=int(timeout)
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
                elif section == "final_answer" and filtered:
                    final_buf.append(filtered)
                elif section == "action_end":
                    self._last_action_payload = "".join(action_buf).strip()
                    break  # 早停：去执行工具
                elif section == "final_answer_end":
                    # 捕获最终答案并提前结束流，避免继续等待无用 token 造成延迟
                    self._last_final_answer = "".join(final_buf).strip()
                    break

                if filtered and filtered.strip():
                    await event_adapter.emit(
                        ReActEvent(
                            ReActEventType.STREAM_CHUNK,
                            {"content": filtered, "type": section or "default"},
                        )
                    )

            # 收尾兜底（未遇到 *_end 标签）
            if action_buf and not self._last_action_payload:
                self._last_action_payload = "".join(action_buf).strip()
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
        if len(obs) > 2000:
            obs = obs[:2000]
        return obs

    async def _reset_stream_markers(self):
        self._last_action_payload = ""
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

    def _extract_fallback_final(self, response: str) -> str:
        # 去掉 action json 片段，只返回可读文本
        if self._last_action_payload:
            try:
                # 删除 action json 片段
                response = response.replace(self._last_action_payload, "")
            except Exception:  # noqa: BLE001
                pass
        return response.strip() or "任务完成"