"""Human-in-the-Loop 使用示例

展示如何在当前架构中集成和使用人工干预功能
"""

import asyncio
from pathlib import Path
import sys

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agent.human_loop import (
    HumanLoopManager,
    RiskBasedApprovalStrategy,
    KeywordApprovalStrategy,
    CLIInteractionHandler,
    ApprovalContext,
)
from src.agent.runtime import ensure_kernel
from src.core.types import Task
from rich.console import Console

console = Console()


async def example_basic_approval():
    """基础审批示例"""
    console.print("[bold blue]示例1: 基础人工审批[/bold blue]\n")

    # 创建Human-in-the-Loop管理器
    interaction_handler = CLIInteractionHandler(console)
    strategies = [
        RiskBasedApprovalStrategy(
            high_risk_tools=["file_write", "system_command"],
            require_final_approval=True,
        )
    ]

    hitl_manager = HumanLoopManager(interaction_handler, strategies)

    # 模拟需要审批的上下文
    context = ApprovalContext(
        action="file_write",
        action_input={"path": "/tmp/test.txt", "content": "Hello World"},
        thought="我需要写入一个文件来保存数据",
        iteration=1,
        metadata={"task_description": "保存数据到文件"},
    )

    console.print("模拟高风险工具调用...")
    approval_response = await hitl_manager.request_approval_if_needed(context)

    if approval_response:
        console.print(f"[green]审批结果: {approval_response.result.value}[/green]")
        if approval_response.message:
            console.print(f"[yellow]反馈: {approval_response.message}[/yellow]")
    else:
        console.print("[green]无需审批，继续执行[/green]")


async def example_keyword_detection():
    """关键词检测示例"""
    console.print("[bold blue]示例2: 敏感关键词检测[/bold blue]\n")

    # 创建基于关键词的策略
    interaction_handler = CLIInteractionHandler(console)
    strategies = [
        KeywordApprovalStrategy(sensitive_keywords=["删除", "清空", "购买", "出售"])
    ]

    hitl_manager = HumanLoopManager(interaction_handler, strategies)

    # 模拟包含敏感关键词的上下文
    context = ApprovalContext(
        action="execute_trade",
        action_input={"symbol": "AAPL", "action": "buy", "quantity": 100},
        thought="用户想要购买100股苹果股票",
        iteration=1,
        metadata={"task_description": "执行股票交易"},
    )

    console.print("模拟包含敏感关键词的操作...")
    approval_response = await hitl_manager.request_approval_if_needed(context)

    if approval_response:
        console.print(f"[green]审批结果: {approval_response.result.value}[/green]")
    else:
        console.print("[green]无敏感关键词，继续执行[/green]")


async def example_final_answer_approval():
    """最终答案审批示例"""
    console.print("[bold blue]示例3: 最终答案审批[/bold blue]\n")

    # 创建需要最终答案确认的策略
    interaction_handler = CLIInteractionHandler(console)
    strategies = [RiskBasedApprovalStrategy(require_final_approval=True)]

    hitl_manager = HumanLoopManager(interaction_handler, strategies)

    # 模拟最终答案
    context = ApprovalContext(
        final_answer="根据分析，建议考虑投资苹果股票(AAPL)，因为其财务状况稳健，市场前景良好。",
        thought="经过深入分析各项指标后得出投资建议",
        iteration=5,
        scratchpad_history=["分析了财务数据", "研究了市场趋势", "评估了风险"],
        metadata={"task_description": "股票投资分析"},
    )

    console.print("模拟最终答案确认...")
    approval_response = await hitl_manager.request_approval_if_needed(context)

    if approval_response:
        console.print(f"[green]审批结果: {approval_response.result.value}[/green]")
        if approval_response.modified_answer:
            console.print(
                f"[blue]修改后的答案: {approval_response.modified_answer}[/blue]"
            )
    else:
        console.print("[green]无需审批，直接输出最终答案[/green]")


async def example_integrated_with_kernel():
    """与AgentKernel集成的完整示例"""
    console.print("[bold blue]示例4: 与AgentKernel完整集成[/bold blue]\n")

    try:
        # 创建启用了Human-in-the-Loop的kernel
        kernel = await ensure_kernel(
            enable_human_loop=True,
            console=console,
            high_risk_tools=["file_write", "system_command"],
            require_final_approval=True,
        )

        # 创建测试任务
        task = Task(
            description="测试Human-in-the-Loop功能", max_iterations=3, timeout=60
        )

        console.print("启动带Human-in-the-Loop的任务执行...")
        console.print("注意: 如果没有配置LLM，此步骤可能失败\n")

        # 执行任务（这里可能会触发人工审批）
        try:
            result = await kernel.execute_task(task)
            console.print(f"[green]任务完成: {result}[/green]")
        except Exception as e:
            console.print(f"[red]任务执行失败: {e}[/red]")
            console.print("[yellow]这可能是因为LLM配置不完整[/yellow]")

    except Exception as e:
        console.print(f"[red]Kernel初始化失败: {e}[/red]")
        console.print("[yellow]请检查LLM配置是否正确[/yellow]")


async def main():
    """主函数"""
    console.print("[bold green]Human-in-the-Loop 功能演示[/bold green]\n")

    examples = [
        ("基础审批", example_basic_approval),
        ("关键词检测", example_keyword_detection),
        ("最终答案审批", example_final_answer_approval),
        ("完整集成", example_integrated_with_kernel),
    ]

    for name, example_func in examples:
        try:
            await example_func()
            console.print("\n" + "=" * 60 + "\n")
        except KeyboardInterrupt:
            console.print(f"\n[yellow]{name} 示例被用户中断[/yellow]\n")
            continue
        except Exception as e:
            console.print(f"[red]{name} 示例执行失败: {e}[/red]\n")
            continue

    console.print("[bold green]演示完成![/bold green]")
    console.print("\n使用方法:")
    console.print("1. 在ask命令中添加 --human-approval 启用人工审批")
    console.print("2. 添加 --require-final-approval 启用最终答案确认")
    console.print("3. 在chat模式中同样适用")
    console.print("\n示例命令:")
    console.print("  python main.py ask '帮我分析一下苹果股票' --human-approval")
    console.print("  python main.py chat --human-approval --require-final-approval")


if __name__ == "__main__":
    asyncio.run(main())
