"""任务执行器"""

import asyncio
import time
from typing import Optional, Callable, Dict, Any, List, Awaitable

from ..core.types import Task
from ..agent.kernel import AgentKernel
from ..core.app_state import app_state
from ..agent.runtime import current_model
from rich import print as rich_print
from rich.console import Console

console = Console()


class TaskExecutor:
    """任务执行器，负责任务的创建和执行"""
    
    def __init__(self, kernel: AgentKernel):
        self.kernel = kernel

    async def run_agent_with_interrupt(
        self,
        question: str,
        *,
        stream: bool = True,
        capture_steps: bool = False,
        minimal: bool = False,
        enable_interrupt: bool = False,
        use_persistent_context: bool = False,
    ) -> dict:
        """运行单个 Agent 任务并返回结果/推理摘要，支持运行时中断。"""
        # 重置中断标志
        app_state.reset_interrupt()

        start_t = time.time()
        progress_lines: List[str] = []

        # 定义进度回调函数
        async def on_progress(chunk: str):
            # 检查是否收到中断请求
            if app_state.interrupt_requested:
                raise asyncio.CancelledError("用户中断")

            if chunk.startswith("[Stream]"):
                text = chunk.replace("[Stream]", "")
                # 使用print直接输出，避免Rich的潜在截断问题
                print(text, end="", flush=True)
            elif not minimal and chunk.startswith("[StreamThinking]"):
                text = chunk.replace("[StreamThinking]", "")
                console.print(f"[dim]{text}[/dim]", end="", highlight=False)
            elif not minimal and chunk.startswith("[StreamAction]"):
                text = chunk.replace("[StreamAction]", "")
                console.print(f"[dim]{text}[/dim]", end="")
            elif not minimal and chunk.startswith("[ThinkingHeader]"):
                console.print("\n[dim]💭 thinking: [/dim]", end="")
            elif not minimal and chunk.startswith("[ActionHeader]"):
                console.print("\n[dim]⚡ action: [/dim]", end="")
            elif not minimal and chunk.startswith("[FinalAnswerHeader]"):
                # 显示最终答案标题和上方横线
                title = "✅ 最终答案"
                console.print(f"\n[bold green]{title}[/bold green]")
                console.print("─" * 50)
            elif not minimal and chunk.startswith("[StreamFinalAnswer]"):
                text = chunk.replace("[StreamFinalAnswer]", "")
                # 最终答案使用正常颜色显示，不用dim
                print(text, end="", flush=True)
            elif not minimal and chunk.startswith("[FinalAnswerEnd]"):
                # 最终答案结束，显示下方横线
                console.print(f"\n{'─' * 50}")
            elif not minimal and chunk.startswith("[StreamThinking]"):
                text = chunk.replace("[StreamThinking]", "")
                console.print(f"[dim]{text}[/dim]", end="")
            elif not minimal and chunk.startswith("[Thinking]"):
                console.print(
                    f"\n[dim]💭 thinking: {chunk.replace('[Thinking]', '').strip()}[/dim]"
                )
            elif not minimal and chunk.startswith("[Action]"):
                console.print(
                    f"\n[dim]⚡ action: {chunk.replace('[Action]', '').strip()}[/dim]"
                )
            # 过滤掉原始的ReAct关键词
            elif not minimal and chunk.strip() in ["Action", "Thought", "Final Answer"]:
                pass  # 忽略这些原始关键词
            if capture_steps and (
                chunk.startswith("[Thinking]") or chunk.startswith("[Action]")
            ):
                progress_lines.append(chunk)

        # 根据模式决定使用什么上下文
        if use_persistent_context:
            # chat 模式：使用持久上下文
            if "conversation_history" not in app_state.persistent_context:
                app_state.persistent_context["conversation_history"] = []

            # 将当前问题添加到对话历史
            app_state.persistent_context["conversation_history"].append(
                {"role": "user", "content": question}
            )

            task = Task(description=question, context=app_state.persistent_context)
        else:
            # ask 模式：使用空上下文
            task = Task(description=question, context={})

        # 创建 agent 执行任务
        app_state.current_task = asyncio.create_task(
            self.kernel.execute_task(task, progress_cb=on_progress, stream=stream)
        )

        try:
            # 等待任务完成
            answer = await app_state.current_task

            # 如果使用持久上下文，保存AI的回答到对话历史
            if use_persistent_context and answer:
                app_state.persistent_context["conversation_history"].append(
                    {"role": "assistant", "content": answer}
                )

                # 限制对话历史长度，避免上下文过长
                max_history_pairs = 8  # 保留最近8轮对话（16条消息）
                if len(app_state.persistent_context["conversation_history"]) > max_history_pairs * 2:
                    # 保留最新的对话，删除最旧的
                    app_state.persistent_context["conversation_history"] = app_state.persistent_context[
                        "conversation_history"
                    ][-(max_history_pairs * 2) :]

        except asyncio.CancelledError:
            if app_state.interrupt_requested:
                raise Exception("任务已被用户中断")
            else:
                raise Exception("任务已被停止")
        finally:
            app_state.current_task = None
            app_state.reset_interrupt()

        latency = round(time.time() - start_t, 3)
        token_usage = task.context.get("token_usage") or {}

        return {
            "answer": answer,
            "model": current_model() or "unknown",
            "latency": latency,
            "reasoning": [],  # 简化处理，实际应该格式化推理步骤
            "_raw_reasoning": progress_lines,
            "tokens": token_usage,
        }