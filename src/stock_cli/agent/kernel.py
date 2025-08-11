"""Agent 核心 - ReAct 任务执行 (重构版)

提供一个清晰、可维护的ReAct执行框架：
    - 职责分离：解析、执行、策略分别模块化
    - 事件驱动：流式输出通过事件系统处理
    - 策略可配置：早停、原子任务检测等策略可替换
    - 通用化：移除特定工具的硬编码优化
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..core.context import ContextManager
from ..core.prompt_loader import PromptBuilder
from ..core.types import AgentConfig, Task, TaskStatus
from ..tools.mcp_server_manager import MCPServerManager

# 导入重构后的模块
from .tool_executor import ToolExecutor
from .events import ReActEvent, ReActEventType, ProgressCallbackAdapter
from .xml_filter import XMLStreamFilter
from .human_loop import HumanLoopManager

logger = logging.getLogger(__name__)

# 禁用 tokenizer 并行警告 (对部分本地模型如 transformers 生效, 安全无副作用)
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class AgentKernel:
    """核心执行器：封装任务生命周期 + ReAct 推理循环

    重构后职责明确：
    - 任务生命周期管理
    - ReAct循环调度
    - 事件发射和进度报告
    - 模块间协调
    """

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

        # 初始化重构后的组件
        self.tool_executor = ToolExecutor()
        self.human_loop_manager = human_loop_manager  # Human-in-the-Loop管理器

        # 任务级 token 累积 (在 execute_task 周期内累加)
        self._token_counters = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

    # =============================
    # Public API
    # =============================
    def _check_completion_from_response(self, response: str) -> bool:
        """检查响应中是否包含final_answer标签（任务完成标志）"""
        return (
            "<final_answer>" in response.lower()
            and "</final_answer>" in response.lower()
        )

    def _extract_final_answer(self, response: str) -> str:
        """从响应中提取final_answer内容"""

        pattern = r"<final_answer>(.*?)</final_answer>"
        match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "任务完成"

    def _extract_action_from_response(self, response: str) -> tuple[str, str]:
        """从响应中提取action内容，返回(action, action_input)"""

        action_pattern = r"<action>(.*?)</action>"
        action_match = re.search(action_pattern, response, re.DOTALL | re.IGNORECASE)

        if action_match:
            action_content = action_match.group(1).strip()
            # 解析action调用格式: tool_name(param=value)
            if "(" in action_content and ")" in action_content:
                action_name = action_content.split("(")[0].strip()
                params_str = action_content[
                    action_content.find("(") + 1 : action_content.rfind(")")
                ]
                return action_name, params_str
            else:
                return action_content, ""
        return "", ""

    async def execute_task(
        self,
        task: Task,
        progress_cb: Optional[Callable[[str], Awaitable[None] | None]] = None,
        *,
        stream: bool = False,
    ) -> Any:
        """执行任务主入口。

        1. 构建上下文 (记忆 / 偏好)
        2.（预留）可选 planner（当前省略以提升响应速度）
        3. 进入 ReAct 循环
        4. 写回结果 + 持久化分析摘要
        """
        task.status = TaskStatus.RUNNING
        # 每个任务开始时重置 tokens
        self._token_counters = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        total_start = time.time()
        total_timeout = min(task.timeout or self.config.timeout, self.config.timeout)

        try:
            # 设置事件适配器
            event_adapter = ProgressCallbackAdapter(progress_cb)

            context = await self.context_manager.build_context_for_task(task)

            # 直接进入 ReAct 循环（简化版，无复杂策略）
            logger.debug("进入 ReAct 循环")

            answer = await self._execute_react_loop(
                task,
                context,
                event_adapter=event_adapter,
                total_start=total_start,
                total_timeout=total_timeout,
                stream=stream,
            )
            task.result = answer
            task.status = TaskStatus.COMPLETED
            # 将 token 统计写入 task.context 供上层读取
            task.context.setdefault("token_usage", dict(self._token_counters))
            return answer

        except Exception as e:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            logger.error(f"任务执行失败: {e}")
            raise

    # =============================
    # ReAct Loop (重构简化版)
    # =============================
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
        """简化的ReAct循环 - 只负责调度，具体逻辑分离到各模块"""
        logger.info(f"开始 ReAct 循环: {task.description[:60]}…")

        iteration = 0
        max_iterations = min(task.max_iterations, self.config.max_iterations)
        consecutive_invalid = 0
        last_action: Optional[str] = None

        while iteration < max_iterations:
            # 超时检查
            if time.time() - total_start > total_timeout:
                logger.warning("达到总体超时限制，终止 ReAct")
                break

            iteration += 1
            task.current_iteration = iteration
            logger.info(f"ReAct 第 {iteration} 轮")

            try:
                # 发射迭代开始事件
                await event_adapter.emit(
                    ReActEvent(ReActEventType.ITERATION_START, {"iteration": iteration})
                )

                # 1. 构建prompt并调用LLM（仅流式输出，无解析）
                response = await self._call_llm_with_stream(
                    task,
                    context,
                    iteration,
                    total_start,
                    total_timeout,
                    stream,
                    event_adapter,
                )

                # 2. 检查是否完成（XML状态机已处理所有输出）
                if self._check_completion_from_response(response):
                    logger.info(f"任务完成 (第 {iteration} 轮)")
                    final_answer = self._extract_final_answer(response)
                    task.scratchpad.append(f"Iteration {iteration}: 任务完成")

                    # 发送最终答案结束事件（用于显示下方横线）
                    if event_adapter:
                        await event_adapter.emit(
                            ReActEvent(
                                ReActEventType.STREAM_CHUNK,
                                {"content": "", "type": "final_answer_end"},
                            )
                        )

                    return final_answer

                # 3. 检查是否需要执行工具
                action_name, action_input = self._extract_action_from_response(response)
                if action_name:
                    # 执行工具调用
                    tool_result = await self.tool_executor.execute(
                        action_name, action_input
                    )

                    # 记录工具执行结果
                    if tool_result.success:
                        observation = f"工具执行成功: {str(tool_result.result)[:200]}"
                    else:
                        observation = f"工具执行失败: {tool_result.error_message}"
                        consecutive_invalid += 1

                    task.scratchpad.append(
                        f"Iteration {iteration}: {action_name}({action_input}) -> {observation}"
                    )
                else:
                    # 没有工具调用，可能是思考或无效响应
                    consecutive_invalid += 1
                    task.scratchpad.append(f"Iteration {iteration}: 无工具调用")

                # 4. 处理上下文总结
                await self._handle_context_summary_if_needed(task)

            except Exception as e:  # noqa: BLE001
                error_msg = f"ReAct 第 {iteration} 轮异常: {e}"
                logger.error(error_msg)
                task.scratchpad.append(f"Error: {error_msg}")

                await event_adapter.emit(
                    ReActEvent(
                        ReActEventType.ERROR, {"error": str(e), "iteration": iteration}
                    )
                )

                if iteration >= max_iterations - 1:
                    break

        # 超过最大迭代次数
        logger.warning(f"达到最大迭代次数 {max_iterations}，任务未完成")
        return "任务结束: 达到迭代/时间限制，部分分析已生成。"

    async def _call_llm_with_stream(
        self,
        task: Task,
        context: Dict[str, Any],
        iteration: int,
        total_start: float,
        total_timeout: float,
        stream: bool,
        event_adapter: ProgressCallbackAdapter,
    ) -> str:
        """调用LLM，支持流式输出"""
        # 获取可用工具
        try:
            mcp_mgr = await MCPServerManager.get_instance()
            mcp_tools = await mcp_mgr.list_tools()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"获取 MCP 工具失败: {e}")
            mcp_tools = []

        # 构建prompt
        available_tools = mcp_tools
        memory_context = context.get("memory_context", "")
        conversation_history = context.get("conversation_history", [])
        prompt = self.prompt_builder.build_react_prompt(
            current_task=task.description,
            scratchpad=task.scratchpad,
            available_tools=available_tools,
            memory_context=memory_context,
            conversation_history=conversation_history,
        )
        messages = [{"role": "user", "content": prompt}]

        # 动态token配置
        base_max = self.config.llm_max_tokens
        dyn_tokens = min(
            1024 if iteration == 1 and not task.scratchpad else 512, base_max
        )

        # 超时配置
        remain_total = total_timeout - (time.time() - total_start)
        if remain_total <= 2:
            logger.warning("剩余时间不足，提前结束")
            raise TimeoutError("剩余时间不足")

        base_min = 15.0 if iteration == 1 else 8.0
        base_cap = 60.0 if iteration == 1 else 30.0
        iter_timeout = min(max(base_min, remain_total - 2), base_cap)

        # 流式或非流式调用
        if stream:
            return await self._stream_llm_call(
                messages, dyn_tokens, iter_timeout, event_adapter
            )
        else:
            return await self._regular_llm_call(messages, dyn_tokens, iter_timeout)

    async def _stream_llm_call(
        self,
        messages: List[Dict],
        max_tokens: int,
        timeout: float,
        event_adapter: ProgressCallbackAdapter,
    ) -> str:
        """流式LLM调用 - 使用XML状态机过滤器"""
        collected: List[str] = []
        xml_filter = XMLStreamFilter()
        thought_header_shown = False
        action_header_shown = False
        final_header_shown = False

        try:
            async for chunk in self.llm_provider.generate_stream(
                messages, max_tokens=max_tokens, timeout=int(timeout)
            ):
                if chunk:
                    collected.append(chunk)

                    # 使用XML状态机过滤器处理chunk
                    filtered_content, section_type = xml_filter.process_chunk(chunk)

                    # 根据section类型发射对应的header事件
                    if section_type == "thought" and not thought_header_shown:
                        await event_adapter.emit(
                            ReActEvent(ReActEventType.THOUGHT_HEADER, {})
                        )
                        thought_header_shown = True
                    elif section_type == "action" and not action_header_shown:
                        await event_adapter.emit(
                            ReActEvent(ReActEventType.ACTION_HEADER, {})
                        )
                        action_header_shown = True
                    elif section_type == "final_answer" and not final_header_shown:
                        await event_adapter.emit(
                            ReActEvent(ReActEventType.FINAL_ANSWER, {"content": ""})
                        )
                        final_header_shown = True

                    # 发射过滤后的内容
                    if filtered_content.strip():
                        await event_adapter.emit(
                            ReActEvent(
                                ReActEventType.STREAM_CHUNK,
                                {
                                    "content": filtered_content,
                                    "type": section_type or "default",
                                },
                            )
                        )

            return "".join(collected)

        except Exception:
            # 流式失败，回退到普通调用
            return await self._regular_llm_call(messages, max_tokens, timeout)

    async def _regular_llm_call(
        self, messages: List[Dict], max_tokens: int, timeout: float
    ) -> str:
        """常规LLM调用"""
        try:
            response = await asyncio.wait_for(
                self.llm_provider.generate(
                    messages, max_tokens=max_tokens, timeout=int(timeout)
                ),
                timeout=timeout + 3,
            )

            # 累计tokens
            usage = getattr(self.llm_provider, "last_usage", None)
            if usage:
                for k in self._token_counters:
                    self._token_counters[k] += int(usage.get(k, 0) or 0)

            return response

        except asyncio.TimeoutError:
            raise TimeoutError("模型调用超时")

    def _build_step_record(self, parsed_step, raw_response: str) -> str:
        """构建步骤记录"""
        return f"Thought: {parsed_step.thought}\n"

    def _handle_tool_result(
        self,
        step_record: str,
        action: str,
        action_input: Dict[str, Any],
        tool_result,
        task: Task,
        iteration: int,
    ) -> str:
        """处理工具执行结果"""
        step_record += f"Action: {action}({action_input})\n"

        if tool_result.success:
            serialized = str(tool_result.result)
            step_record += f"Observation: 成功 -> {serialized[:500]}"
        else:
            step_record += f"Observation: 工具执行失败: {tool_result.error_message}"

        return step_record

    async def _handle_context_summary_if_needed(self, task: Task):
        """简化的上下文处理 - 基本的长度检查"""
        # 简单的长度检查，如果scratchpad过长就截取最后几条
        if len(task.scratchpad) > 20:
            logger.info("截取执行轨迹")
            task.scratchpad = task.scratchpad[-10:]  # 保留最后10条

    # 保留兼容性的综合分析方法（未来可能移除）
    async def _synthesize_results(
        self, task: Task, results: List[str], context: Dict[str, Any]
    ) -> str:
        """综合分析多个子任务的结果"""
        try:
            logger.info("开始综合分析")

            # 合并所有结果
            collected_info = "\n\n---\n\n".join(
                [
                    f"分析结果 {i + 1}:\n{result}"
                    for i, result in enumerate(results)
                    if result
                ]
            )

            # 使用综合分析器
            prompt = self.prompt_builder.build_synthesizer_prompt(
                original_task=task.description, collected_information=collected_info
            )

            messages = [{"role": "user", "content": prompt}]
            final_analysis = await self.llm_provider.generate(messages)
            usage = getattr(self.llm_provider, "last_usage", None)
            if usage:
                for k in self._token_counters:
                    self._token_counters[k] += int(usage.get(k, 0) or 0)

            logger.info("综合分析完成")
            return final_analysis

        except Exception as e:
            logger.error(f"综合分析失败: {e}")
            return "综合分析失败，但各子任务结果如下：\n\n" + "\n\n".join(results)
