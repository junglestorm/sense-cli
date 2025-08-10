"""简化的ReAct执行策略

减少硬编码策略逻辑，更多依赖模型的智能判断
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class ExecutionStrategies:
    """简化的执行策略集合 - 主要依赖模型智能而非硬编码规则"""
    
    def __init__(self):
        self.summary_threshold = 8000  # 上下文总结阈值
        self.max_consecutive_failures = 3  # 最大连续失败次数
    
    def check_early_stop(self, context: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """简化的早停检查 - 减少硬编码规则"""
        # 移除复杂的关键词检测，让模型自己决定何时停止
        return False, None
    
    def handle_consecutive_failures(self, consecutive_failures: int, max_iterations: int, 
                                  current_iteration: int) -> Optional[str]:
        """处理连续失败 - 简化逻辑"""
        if (consecutive_failures >= self.max_consecutive_failures and 
            current_iteration < max_iterations):
            return ("Observation: 连续工具调用失败，请检查工具名称和参数格式，"
                    "或者如果已有足够信息则直接给出最终答案。")
        return None
    
    def handle_short_task_fallback(self, task_description: str, iteration: int, 
                                 has_action: bool, scratchpad: List[str], thought: str) -> Optional[str]:
        """简化的短任务回退策略"""
        # 简化判断逻辑，让模型自己决定
        if (iteration == 1 and 
            not has_action and 
            len(task_description) < 50 and 
            len(scratchpad) <= 1):
            return thought or "任务完成"
        return None
    
    def handle_context_summary(self, scratchpad: List[str]) -> tuple[bool, str, List[str]]:
        """处理上下文总结"""
        total_length = sum(len(step) for step in scratchpad)
        
        if total_length > self.summary_threshold:
            # 保留最后几步的详细信息
            recent_steps = scratchpad[-3:] if len(scratchpad) > 3 else scratchpad
            content_to_summarize = "\n\n".join(scratchpad)
            return True, content_to_summarize, recent_steps
        
        return False, "", []
    
    @property
    def short_task_strategy(self):
        """兼容性属性 - 简化实现"""
        return SimpleTaskStrategy()
    
    @property  
    def summary_strategy(self):
        """兼容性属性 - 简化实现"""
        return SimpleSummaryStrategy()


class SimpleTaskStrategy:
    """简化的任务策略"""
    
    def is_short_task(self, task_description: str) -> bool:
        """简单判断是否为短任务"""
        return len(task_description.strip()) < 60


class SimpleSummaryStrategy:
    """简化的总结策略"""
    
    def apply_summary(self, scratchpad: List[str], summary: str, recent_steps: List[str]) -> List[str]:
        """应用总结结果"""
        return [f"[总结前面的步骤] {summary}"] + recent_steps
