from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from ..core.context import ContextManager
from ..core.prompt_loader import PromptBuilder
from ..core.types import AgentConfig, Task, TaskStatus
from ..tools.mcp_server_manager import MCPServerManager
from .events import ReActEvent, ReActEventType, ProgressCallbackAdapter
from .xml_filter import XMLStreamFilter
from .human_loop import HumanLoopManager

logger = logging.getLogger(__name__)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


TOOL_POLICY = (
    "Tool use policy:\n"
    "1. 在 <action> 中输出严格 JSON: {\"tool\": \"name\", \"arguments\": {...}} (双引号, 无多余文本)。\n"
    "2. 每轮至多一个 <action>；如信息足够可直接输出 <final_answer>。\n"
    "3. 避免重复调用同一工具+参数；若已有结果请直接利用生成答案。\n"
    "4. 通常不应超过 3 次工具调用，尽早给出 <final_answer>。\n"
    "5. 工具失败可做一次合理修正；再失败或无必要继续请直接 <final_answer> 解释。\n"
)


class AgentKernel:
    def __init__(
        self,
        llm_provider,
        context_manager: ContextManager,
        prompt_builder: PromptBuilder,
        config: AgentConfig,
        human_loop_manager: Optional[HumanLoopManager] = None,
    ):
        self.llm_provider = llm_provider
        self.context_manager = context_manager
        self.prompt_builder = prompt_builder
        self.config = config
        self.human_loop_manager = human_loop_manager
        self._token_counters = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self._last_action_payload: str = ""
        self._last_final_answer: str = ""

    # ---------------- 公共入口 ----------------
    async def execute_task(
        self,
        task: Task,
        progress_cb: Optional[Callable[[str], Awaitable[None] | None]] = None,
        *,
        stream: bool = False,
    ) -> Any:
        task.status = TaskStatus.RUNNING
        self._token_counters = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        total_start = time.time()
        total_timeout = min(task.timeout or self.config.timeout, self.config.timeout)
        event_adapter = ProgressCallbackAdapter(progress_cb)
        try:
            context = await self.context_manager.build_context_for_task(task)
            task.context.setdefault("chat_messages", [])
            task.context.setdefault("tool_calls_count", 0)
            result = await self._execute_react_loop(
                task,
                context,
                event_adapter=event_adapter,
                total_start=total_start,
                total_timeout=total_timeout,
                stream=stream,
            )
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.context.setdefault("token_usage", dict(self._token_counters))

            # 写入对话历史到文件
            self._write_chat_history_to_file(task)

            return result
        except Exception as e:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            logger.exception("任务执行失败")

            # 写入对话历史到文件，即使任务失败
            self._write_chat_history_to_file(task)

            raise

    def _write_chat_history_to_file(self, task: Task):
        """将对话历史写入文件"""
        try:
            chat_history = task.context.get("chat_messages", [])
            if not chat_history:
                return

            # 生成文件名，基于任务 ID 或时间戳
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            file_name = f"chat_history_{task.id or timestamp}.json"
            file_path = os.path.join("logs", file_name)

            # 写入文件
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(chat_history, f, ensure_ascii=False, indent=4)

            logger.info(f"对话历史已写入文件: {file_path}")
        except Exception as e:
            logger.error(f"写入对话历史失败: {e}")

    # ---------------- ReAct 主循环 ----------------
    async def _execute_react_loop(
        self,
        task: Task,
        context: Dict[str, Any],
        event_adapter: ProgressCallbackAdapter,
        *,
        total_start: float,
        total_timeout: float,
        stream: bool = False,
    ) -> str:
        logger.info("开始 ReAct 循环: %s", task.description[:80])
        iteration = 0
        max_iterations = task.max_iterations

        while iteration < max_iterations:
            if time.time() - total_start > total_timeout:
                logger.warning("达到总体超时限制，提前终止")
                break
            iteration += 1
            task.current_iteration = iteration
            await event_adapter.emit(ReActEvent(ReActEventType.ITERATION_START, {"iteration": iteration}))

            # 1. 第一次模型调用（可能给出 action 或 直接 final_answer）
            await self._reset_stream_markers()
            response_text = await self._call_llm_with_stream(
                task, context, iteration, total_start, total_timeout, stream, event_adapter, post_tool_hint=False
            )

            if self._last_final_answer:
                final_answer = self._last_final_answer.strip()
                # 将 final_answer 写入 assistant 历史
                task.context['chat_messages'].append({
                    "role": "assistant",
                    "content": f"<final_answer>{final_answer}</final_answer>"
                })
                await event_adapter.emit(
                    ReActEvent(ReActEventType.STREAM_CHUNK, {"content": "", "type": "final_answer_end"})
                )
                task.scratchpad.append(f"Iteration {iteration}: 直接完成")
                return final_answer

            action_name, action_args = self._parse_action_json(self._last_action_payload)
            if not action_name:
                # 没有 action 也没有 final_answer -> 视为模型直接回答但未包裹 final 标签，兜底
                fallback = self._extract_fallback_final(response_text)
                await event_adapter.emit(
                    ReActEvent(ReActEventType.STREAM_CHUNK, {"content": "", "type": "final_answer_end"})
                )
                task.scratchpad.append(f"Iteration {iteration}: Fallback 完成")
                return fallback

            # 2. 执行工具
            observation_text = await self._run_tool_and_record(
                task, action_name, action_args, event_adapter, iteration
            )

            # 3. 第二次模型调用（同一迭代内），带 post-tool hint
            await self._reset_stream_markers()
            response2 = await self._call_llm_with_stream(
                task, context, iteration, total_start, total_timeout, stream, event_adapter, post_tool_hint=True
            )

            if self._last_final_answer:
                final_answer = self._last_final_answer.strip()
                # 将 final_answer 写入 assistant 历史
                task.context['chat_messages'].append({
                    "role": "assistant",
                    "content": f"<final_answer>{final_answer}</final_answer>"
                })
                await event_adapter.emit(
                    ReActEvent(ReActEventType.STREAM_CHUNK, {"content": "", "type": "final_answer_end"})
                )
                task.scratchpad.append(
                    f"Iteration {iteration}: 工具后完成 ({action_name})"
                )
                return final_answer

            # 若仍然只是新的 action，则进入下一轮（下一个 while 迭代）
            next_action_name, next_action_args = self._parse_action_json(self._last_action_payload)
            if next_action_name:
                task.scratchpad.append(
                    f"Iteration {iteration}: 链式继续 -> {next_action_name}({next_action_args})"
                )
                await self._handle_context_summary_if_needed(task)
                continue

            # 二次仍无 final_answer，无动作：兜底把模型输出作为最终答案
            fallback2 = self._extract_fallback_final(response2)
            # 将 fallback final_answer 写入 assistant 历史
            task.context['chat_messages'].append({
                "role": "assistant",
                "content": f"<final_answer>{fallback2}</final_answer>"
            })
            await event_adapter.emit(
                ReActEvent(ReActEventType.STREAM_CHUNK, {"content": "", "type": "final_answer_end"})
            )
            task.scratchpad.append(
                f"Iteration {iteration}: 二次回合兜底完成 (tool={action_name})"
            )
            return fallback2

        logger.warning("达到最大迭代次数 %d 未完成", task.max_iterations)
        return "任务结束: 达到迭代/时间限制。"

    # ---------------- 消息与模型调用 ----------------
    async def _call_llm_with_stream(
        self,
        task: Task,
        context: Dict[str, Any],
        iteration: int,
        total_start: float,
        total_timeout: float,
        stream: bool,
        event_adapter: ProgressCallbackAdapter,
        *,
        post_tool_hint: bool,
    ) -> str:
        messages = await self._build_messages(task, context, post_tool_hint=post_tool_hint)

        # token / timeout 动态配置
        remain_total = total_timeout - (time.time() - total_start)
        if remain_total <= 1.5:
            raise TimeoutError("剩余时间不足")

        base_max = self.config.llm_max_tokens
        dyn_tokens = min(1024 if iteration == 1 and not task.scratchpad else 512, base_max)
        base_min = 12.0 if iteration == 1 else 6.0
        base_cap = 50.0 if iteration == 1 else 25.0
        iter_timeout = min(max(base_min, remain_total - 1.5), base_cap)

        if stream:
            return await self._stream_llm_call(messages, dyn_tokens, iter_timeout, event_adapter)
        return await self._regular_llm_call(messages, dyn_tokens, iter_timeout)

    async def _build_messages(self, task: Task, context: Dict[str, Any], *, post_tool_hint: bool) -> List[Dict[str, str]]:
        # 工具列表
        try:
            mcp_mgr = await MCPServerManager.get_instance()
            tools = await mcp_mgr.list_tools()
        except Exception as e:  # noqa: BLE001
            logger.warning("获取 MCP 工具失败: %s", e)
            tools = []

        tool_names = [getattr(t, "name", "unknown") for t in tools]
        tools_desc = []
        for t in tools:
            try:
                if hasattr(t, "format_for_llm"):
                    tools_desc.append(t.format_for_llm())
                else:
                    tools_desc.append(
                        f"Tool: {getattr(t,'name','unknown')}\nDescription: {getattr(t,'description','')}"
                    )
            except Exception:
                pass

        memory_context = context.get("memory_context", "")
        conversation_history = context.get("conversation_history", [])
        react_prompt = self.prompt_builder.build_react_prompt(
            current_task=task.description,
            scratchpad=task.scratchpad,
            available_tools=tools,
            memory_context=memory_context,
            conversation_history=conversation_history,
        )

        post_tool_extra = (
            "\n先前工具观察结果已在历史中。若已足够回答，请直接输出 <final_answer>。"
            " 如仍需要额外信息再输出新的 <action>。"
            if post_tool_hint
            else ""
        )

        system_tools = (
            f"Available tool names: {', '.join(tool_names) if tool_names else 'none'}\n\n" +
            "可用工具：\n" + "\n".join(tools_desc)
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": TOOL_POLICY},
            {"role": "system", "content": system_tools},
        ]

        history = task.context.get("chat_messages") or []
        if isinstance(history, list):
            messages.extend([m for m in history if isinstance(m, dict) and m.get("role") and m.get("content")])

        messages.append({"role": "user", "content": react_prompt + post_tool_extra})

        # 确保 user 消息写入 chat_messages
        task.context['chat_messages'].append({
            "role": "user",
            "content": react_prompt + post_tool_extra
        })

        return messages

    async def _stream_llm_call(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        timeout: float,
        event_adapter: ProgressCallbackAdapter,
    ) -> str:
        xml_filter = XMLStreamFilter()
        collected: List[str] = []
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
                if section == "thought" and not thought_shown:
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
                    self._last_final_answer = "".join(final_buf).strip()

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
            logger.warning("流式失败回退: %s", e)
            return await self._regular_llm_call(messages, max_tokens, timeout)

    async def _regular_llm_call(self, messages: List[Dict[str, str]], max_tokens: int, timeout: float) -> str:
        try:
            resp = await asyncio.wait_for(
                self.llm_provider.generate(messages, max_tokens=max_tokens, timeout=int(timeout)),
                timeout=timeout + 3,
            )
        except asyncio.TimeoutError as e:  # noqa: PERF203
            raise TimeoutError("模型调用超时") from e

        usage = getattr(self.llm_provider, "last_usage", None)
        if usage:
            for k in self._token_counters:
                self._token_counters[k] += int(usage.get(k, 0) or 0)

        # 简单解析 final_answer（非流式 fallback）
        m = re.search(r"<final_answer>([\s\S]*?)</final_answer>", resp)
        if m:
            self._last_final_answer = m.group(1).strip()
        else:
            m2 = re.search(r"<action>([\s\S]*?)</action>", resp)
            if m2:
                self._last_action_payload = m2.group(1).strip()
        return resp

    # ---------------- 工具执行与辅助 ----------------
    async def _run_tool_and_record(
        self,
        task: Task,
        action: str,
        arguments: Dict[str, Any],
        event_adapter: ProgressCallbackAdapter,
        iteration: int,
    ) -> str:
        chat_messages: List[Dict[str, str]] = task.context.setdefault("chat_messages", [])
        call_json = json.dumps({"tool": action, "arguments": arguments}, ensure_ascii=False)
        chat_messages.append({"role": "assistant", "content": call_json})
        task.scratchpad.append(f"ToolCall: {call_json}")
        try:
            mgr = await MCPServerManager.get_instance()
            raw_result = await mgr.call_tool(action, arguments or {})
            try:
                serialized = json.dumps(raw_result, ensure_ascii=False)
            except Exception:
                serialized = str(raw_result)
            observation = serialized[:2000]
            # 使用 assistant 角色存储工具结果，避免底层 API 对 tool 消息的额外字段要求
            chat_messages.append({"role": "assistant", "content": f"<tool_result name=\"{action}\">{observation}</tool_result>"})
            await event_adapter.emit(
                ReActEvent(ReActEventType.STREAM_CHUNK, {"content": observation, "type": "observation"})
            )
            task.scratchpad.append(
                f"Iteration {iteration}: {action} -> 成功"
            )
            task.context["tool_calls_count"] = int(task.context.get("tool_calls_count", 0) or 0) + 1
            return observation
        except Exception as e:  # noqa: BLE001
            err = f"ERROR: {e}"
            chat_messages.append({"role": "assistant", "content": f"<tool_result name=\"{action}\">{err}</tool_result>"})
            await event_adapter.emit(
                ReActEvent(ReActEventType.STREAM_CHUNK, {"content": err, "type": "observation"})
            )
            task.scratchpad.append(
                f"Iteration {iteration}: {action} -> 失败 {e}"
            )
            # 给模型一个自然的下一步引导
            chat_messages.append({
                "role": "assistant",
                "content": "工具调用失败。请只在确有必要时再尝试一次修正，否则直接输出 <final_answer> 总结。",
            })
            return err

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

    # 兼容：保留旧接口（尽管重构后内部实现已变化）
    def _build_step_record(self, parsed_step, raw_response: str) -> str:  # noqa: D401
        return f"Thought: {getattr(parsed_step, 'thought', '')}\n"

    def _handle_tool_result(
        self,
        step_record: str,
        action: str,
        action_input: Dict[str, Any],
        tool_result,
        task: Task,
        iteration: int,
    ) -> str:  # noqa: D401
        return step_record + f"Action: {action}({action_input})\n"

    async def _handle_context_summary_if_needed(self, task: Task):
        if len(task.scratchpad) > 60:
            task.scratchpad = task.scratchpad[-30:]
        history = task.context.get("chat_messages")
        if isinstance(history, list) and len(history) > 80:
            task.context["chat_messages"] = history[-50:]

    # 综合分析（保留兼容）
    async def _synthesize_results(self, task: Task, results: List[str], context: Dict[str, Any]) -> str:
        try:
            merged = "\n\n---\n\n".join([f"分析 {i+1}:\n{r}" for i, r in enumerate(results) if r])
            prompt = self.prompt_builder.build_synthesizer_prompt(
                original_task=task.description, collected_information=merged
            )
            messages = [{"role": "user", "content": prompt}]
            resp = await self.llm_provider.generate(messages)
            usage = getattr(self.llm_provider, "last_usage", None)
            if usage:
                for k in self._token_counters:
                    self._token_counters[k] += int(usage.get(k, 0) or 0)
            return resp
        except Exception as e:  # noqa: BLE001
            logger.warning("综合分析失败: %s", e)
            return "综合分析失败\n" + "\n".join(results)
