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
    ):
        self.llm_provider = llm_provider
        self.context_manager = context_manager
        self.prompt_builder = prompt_builder
        self.config = config
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
    
    def _output_callback(self,stub:str):
        "处理模型输出各个字段的回调，包括上下文处理、工具执行或者特殊的task流程处理"
        match stub:
            case "action":
                pass
            case "final_answer":
                pass
            case "thinking":
                pass

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

            # 单次模型调用
            await self._reset_stream_markers()
            
            # 构建消息并直接调用流式接口
            messages = await self._build_messages(task, context, post_tool_hint=True)
            response_text = await self._stream_llm_call(
                messages, 
                self.config.llm_max_tokens, 
                total_timeout - (time.time() - total_start), 
                event_adapter
            )

            # 执行相应的处理方法
            result = await self._handle_final_answer(task, event_adapter, iteration)
            if result is not None:
                return result
                
            result = await self._handle_action(task, event_adapter, iteration)
            if result is not None:
                return result
                
            result = await self._handle_fallback(task, event_adapter, iteration, response_text)
            if result is not None:
                return result
                
            await self._handle_context_summary_if_needed(task)

        logger.warning("达到最大迭代次数 %d 未完成", max_iter)
        return "任务结束: 达到迭代/时间限制。"

    async def _handle_final_answer(self, task: Task, event_adapter: ProgressCallbackAdapter, iteration: int) -> Optional[str]:
        """处理 final_answer 情况"""
        if self._last_final_answer:
            final_answer = self._last_final_answer.strip()
            task.context['chat_messages'].append({
                "role": "assistant",
                "content": f"<final_answer>{final_answer}</final_answer>"
            })
            await event_adapter.emit(
                ReActEvent(ReActEventType.STREAM_CHUNK, {"content": "", "type": "final_answer_end"})
            )
            task.scratchpad.append(f"Iteration {iteration}: 完成")
            return final_answer
        return None

    async def _handle_action(self, task: Task, event_adapter: ProgressCallbackAdapter, iteration: int) -> Optional[str]:
        """处理 action 情况"""
        # 情况 B: 解析到 action
        action_name, action_args = self._parse_action_json(self._last_action_payload)
        if action_name and self._last_action_payload:
            await self._run_tool_and_record(task, action_name, action_args, event_adapter, iteration)
            await self._handle_context_summary_if_needed(task)
            return None  # 返回 None 表示继续下一轮迭代
        return None

    async def _handle_fallback(self, task: Task, event_adapter: ProgressCallbackAdapter, iteration: int, response_text: str) -> Optional[str]:
        """处理 fallback 情况"""
        # 情况 C: 既没有 final 也没有 action -> 直接把模型原文当答案
        action_name, _ = self._parse_action_json(self._last_action_payload)
        if not self._last_final_answer and not action_name:
            fallback_raw = self._extract_fallback_final(response_text)
            # 记录模型原文（不包裹 final 标签）
            task.context['chat_messages'].append({
                "role": "assistant",
                "content": fallback_raw
            })
            # 注入提示，指导其规范输出 action 或 final_answer
            task.context['chat_messages'].append({
                "role": "user",
                "content": (
                    "上一次输出未提供 <action> 或 <final_answer>。请按策略：\n"
                    "1) 若需要调用工具：输出 <action>{\"tool\":\"name\",\"arguments\":{...}}</action>\n"
                    "2) 若可以直接回答：输出 <final_answer>答案内容</final_answer>\n"
                    "不要再输出其它说明文字。"
                )
            })
            task.scratchpad.append(f"Iteration {iteration}: 无标签 -> 反馈再试")
            await self._handle_context_summary_if_needed(task)
            return None  # 返回 None 表示继续下一轮迭代
        return None

    # ---------------- 消息与模型调用 ----------------

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
                if section == "thingking" and not thought_shown:
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



