"""Human-in-the-Loop 系统

为ReAct执行过程提供人工干预和审批功能
"""

import asyncio
import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod


logger = logging.getLogger(__name__)


class ApprovalType(Enum):
    """审批类型"""

    TOOL_EXECUTION = "tool_execution"
    HIGH_RISK_ACTION = "high_risk_action"
    ITERATION_CHECKPOINT = "iteration_checkpoint"
    FINAL_ANSWER = "final_answer"
    CUSTOM_INTERVENTION = "custom_intervention"


class ApprovalResult(Enum):
    """审批结果"""

    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    CANCELLED = "cancelled"


@dataclass
class ApprovalContext:
    """审批上下文信息"""

    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    tool_description: Optional[str] = None
    risk_level: str = "low"
    iteration: int = 0
    scratchpad_history: List[str] = field(default_factory=list)
    thought: Optional[str] = None
    final_answer: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ApprovalRequest:
    """审批请求"""

    approval_type: ApprovalType
    context: ApprovalContext
    message: str
    timeout_seconds: float = 300.0  # 5分钟默认超时
    allow_modification: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class ApprovalResponse:
    """审批响应"""

    result: ApprovalResult
    message: Optional[str] = None
    modified_action: Optional[str] = None
    modified_input: Optional[Dict[str, Any]] = None
    modified_answer: Optional[str] = None
    response_time: float = field(default_factory=time.time)


class HumanApprovalStrategy(ABC):
    """人工审批策略抽象基类"""

    @abstractmethod
    def should_request_approval(
        self, context: ApprovalContext
    ) -> tuple[bool, ApprovalType, str]:
        """判断是否需要人工审批

        Returns:
            (needs_approval, approval_type, reason)
        """
        pass


class RiskBasedApprovalStrategy(HumanApprovalStrategy):
    """基于风险的审批策略"""

    def __init__(
        self,
        high_risk_tools: List[str] = None,
        require_final_approval: bool = False,
        checkpoint_intervals: int = 5,
    ):
        self.high_risk_tools = high_risk_tools or [
            "execute_trade",
            "send_email",
            "file_write",
            "system_command",
        ]
        self.require_final_approval = require_final_approval
        self.checkpoint_intervals = checkpoint_intervals

    def should_request_approval(
        self, context: ApprovalContext
    ) -> tuple[bool, ApprovalType, str]:
        """基于风险评估是否需要审批"""

        # 1. 高风险工具检查
        if context.action and context.action in self.high_risk_tools:
            return True, ApprovalType.HIGH_RISK_ACTION, f"高风险工具: {context.action}"

        # 2. 最终答案确认
        if self.require_final_approval and context.final_answer:
            return True, ApprovalType.FINAL_ANSWER, "需要确认最终答案"

        # 3. 检查点间隔
        if (
            self.checkpoint_intervals > 0
            and context.iteration > 0
            and context.iteration % self.checkpoint_intervals == 0
        ):
            return (
                True,
                ApprovalType.ITERATION_CHECKPOINT,
                f"第{context.iteration}轮检查点",
            )

        return False, ApprovalType.TOOL_EXECUTION, ""


class KeywordApprovalStrategy(HumanApprovalStrategy):
    """基于关键词的审批策略"""

    def __init__(self, sensitive_keywords: List[str] = None):
        self.sensitive_keywords = sensitive_keywords or [
            "删除",
            "清空",
            "格式化",
            "重置",
            "购买",
            "出售",
            "转账",
        ]

    def should_request_approval(
        self, context: ApprovalContext
    ) -> tuple[bool, ApprovalType, str]:
        """基于敏感关键词判断"""
        text_to_check = []

        if context.thought:
            text_to_check.append(context.thought)
        if context.action:
            text_to_check.append(context.action)
        if context.action_input:
            text_to_check.append(str(context.action_input))
        if context.final_answer:
            text_to_check.append(context.final_answer)

        full_text = " ".join(text_to_check).lower()

        for keyword in self.sensitive_keywords:
            if keyword.lower() in full_text:
                return (
                    True,
                    ApprovalType.HIGH_RISK_ACTION,
                    f"检测到敏感关键词: {keyword}",
                )

        return False, ApprovalType.TOOL_EXECUTION, ""


class InteractionHandler(ABC):
    """人工交互处理器抽象基类"""

    @abstractmethod
    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """请求人工审批"""
        pass


class CLIInteractionHandler(InteractionHandler):
    """命令行交互处理器"""

    def __init__(self, console=None):
        from rich.console import Console

        self.console = console or Console()

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """通过命令行请求人工审批"""
        try:
            # 显示审批请求
            self._display_approval_request(request)

            # 等待用户输入（在单独的线程中运行以避免阻塞）
            loop = asyncio.get_event_loop()

            # 使用超时的输入
            try:
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, self._get_user_input, request),
                    timeout=request.timeout_seconds,
                )
                return response
            except asyncio.TimeoutError:
                self.console.print(
                    f"[yellow]审批请求超时({request.timeout_seconds}s)，自动拒绝[/yellow]"
                )
                return ApprovalResponse(
                    result=ApprovalResult.REJECTED, message="超时自动拒绝"
                )

        except Exception as e:
            logger.error(f"人工审批过程异常: {e}")
            return ApprovalResponse(
                result=ApprovalResult.REJECTED, message=f"审批过程异常: {e}"
            )

    def _display_approval_request(self, request: ApprovalRequest):
        """显示审批请求"""
        from rich.panel import Panel
        from rich.text import Text

        # 构建显示内容
        content = Text()
        content.append(f"审批类型: {request.approval_type.value}\n", style="bold")
        content.append(f"消息: {request.message}\n\n", style="yellow")

        ctx = request.context
        if ctx.action:
            content.append(f"工具: {ctx.action}\n", style="cyan")
            if ctx.action_input:
                content.append(f"参数: {ctx.action_input}\n", style="dim")

        if ctx.thought:
            content.append(f"思考: {ctx.thought[:200]}...\n", style="green")

        if ctx.final_answer:
            content.append(f"最终答案: {ctx.final_answer[:200]}...\n", style="magenta")

        # 显示面板
        panel = Panel(
            content, title="🤔 需要人工审批", title_align="left", border_style="red"
        )
        self.console.print(panel)

    def _get_user_input(self, request: ApprovalRequest) -> ApprovalResponse:
        """获取用户输入（同步方法）"""
        while True:
            # 显示选项
            options = "[green]y[/green]es, [red]n[/red]o"
            if request.allow_modification:
                options += ", [blue]m[/blue]odify"
            options += ", [yellow]c[/yellow]ancel"

            self.console.print(f"选择: {options}")

            try:
                user_input = input("> ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return ApprovalResponse(
                    result=ApprovalResult.CANCELLED, message="用户中断"
                )

            if user_input in ["y", "yes", "是", "ok"]:
                return ApprovalResponse(
                    result=ApprovalResult.APPROVED, message="用户批准"
                )

            elif user_input in ["n", "no", "否", "reject"]:
                return ApprovalResponse(
                    result=ApprovalResult.REJECTED, message="用户拒绝"
                )

            elif user_input in ["c", "cancel", "取消"]:
                return ApprovalResponse(
                    result=ApprovalResult.CANCELLED, message="用户取消"
                )

            elif user_input in ["m", "modify", "修改"] and request.allow_modification:
                return self._handle_modification(request)

            else:
                self.console.print("[red]无效输入，请重新选择[/red]")

    def _handle_modification(self, request: ApprovalRequest) -> ApprovalResponse:
        """处理修改请求"""
        self.console.print("[blue]请提供修改内容:[/blue]")

        try:
            modification = input("修改内容: ").strip()
            if not modification:
                return ApprovalResponse(
                    result=ApprovalResult.REJECTED, message="修改内容为空"
                )

            # 根据审批类型决定修改什么
            if request.approval_type == ApprovalType.FINAL_ANSWER:
                return ApprovalResponse(
                    result=ApprovalResult.MODIFIED,
                    modified_answer=modification,
                    message="最终答案已修改",
                )
            else:
                # 简单起见，将修改内容作为新的action
                return ApprovalResponse(
                    result=ApprovalResult.MODIFIED,
                    modified_action=modification,
                    message="操作已修改",
                )

        except (EOFError, KeyboardInterrupt):
            return ApprovalResponse(
                result=ApprovalResult.CANCELLED, message="修改被中断"
            )


class HumanLoopManager:
    """Human-in-the-Loop 管理器"""

    def __init__(
        self,
        interaction_handler: InteractionHandler,
        strategies: List[HumanApprovalStrategy] = None,
    ):
        self.interaction_handler = interaction_handler
        self.strategies = strategies or [RiskBasedApprovalStrategy()]
        self.enabled = True

    def enable(self):
        """启用人工干预"""
        self.enabled = True
        logger.info("Human-in-the-Loop 已启用")

    def disable(self):
        """禁用人工干预"""
        self.enabled = False
        logger.info("Human-in-the-Loop 已禁用")

    async def check_approval_needed(
        self, context: ApprovalContext
    ) -> Optional[ApprovalRequest]:
        """检查是否需要人工审批"""
        if not self.enabled:
            return None

        for strategy in self.strategies:
            needs_approval, approval_type, reason = strategy.should_request_approval(
                context
            )
            if needs_approval:
                logger.info(f"需要人工审批: {reason}")
                return ApprovalRequest(
                    approval_type=approval_type,
                    context=context,
                    message=reason,
                    allow_modification=(
                        approval_type != ApprovalType.ITERATION_CHECKPOINT
                    ),
                )

        return None

    async def request_approval_if_needed(
        self, context: ApprovalContext
    ) -> Optional[ApprovalResponse]:
        """如果需要则请求人工审批"""
        request = await self.check_approval_needed(context)
        if not request:
            return None

        logger.info(f"请求人工审批: {request.message}")
        response = await self.interaction_handler.request_approval(request)
        logger.info(f"审批结果: {response.result.value}")

        return response


# 便利函数：创建默认的HITL配置
def create_default_human_loop(
    console=None,
    high_risk_tools: List[str] = None,
    require_final_approval: bool = False,
) -> HumanLoopManager:
    """创建默认的Human-in-the-Loop配置"""

    # 创建策略
    strategies = [
        RiskBasedApprovalStrategy(
            high_risk_tools=high_risk_tools,
            require_final_approval=require_final_approval,
        ),
        KeywordApprovalStrategy(),
    ]

    # 创建交互处理器
    interaction_handler = CLIInteractionHandler(console=console)

    # 创建管理器
    return HumanLoopManager(interaction_handler, strategies)
