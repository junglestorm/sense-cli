"""Human-in-the-Loop 配置示例

展示不同的Human-in-the-Loop配置选项
"""

# config/human_loop_config.yaml
human_loop_config_example = """
# Human-in-the-Loop 配置示例
human_loop:
  # 是否启用人工干预
  enabled: false
  
  # 风险等级配置
  risk_levels:
    # 高风险工具列表（需要人工确认）
    high_risk_tools:
      - "file_write"
      - "file_delete"  
      - "system_command"
      - "execute_trade"
      - "send_email"
      - "database_write"
    
    # 敏感关键词列表
    sensitive_keywords:
      - "删除"
      - "清空"
      - "格式化"
      - "重置"
      - "购买"
      - "出售"
      - "转账"
      - "支付"
    
  # 审批策略配置
  approval_strategies:
    # 基于风险的审批
    risk_based:
      enabled: true
      require_final_approval: false  # 是否需要最终答案确认
      checkpoint_intervals: 5        # 每N轮进行检查点确认
    
    # 基于关键词的审批
    keyword_based:
      enabled: true
      case_sensitive: false
    
    # 自定义审批规则
    custom_rules:
      - condition: "action == 'file_write' and 'system' in action_input.path"
        message: "尝试写入系统目录"
        approval_type: "high_risk_action"
      - condition: "final_answer and len(final_answer) > 1000"
        message: "最终答案过长，需要确认"
        approval_type: "final_answer"
  
  # 交互配置
  interaction:
    # 超时设置（秒）
    timeout_seconds: 300
    
    # 是否允许修改
    allow_modification: true
    
    # 超时后的默认行为（approved/rejected/cancelled）
    timeout_default_action: "rejected"
    
    # 界面样式
    ui:
      show_context_details: true
      show_risk_assessment: true
      color_scheme: "auto"  # auto/light/dark

# 预设配置模板
presets:
  # 开发模式：较宽松的审批
  development:
    enabled: true
    risk_based:
      require_final_approval: false
      checkpoint_intervals: 10
    keyword_based:
      enabled: false
    interaction:
      timeout_seconds: 60
      timeout_default_action: "approved"
  
  # 生产模式：严格的审批
  production:
    enabled: true
    risk_based:
      require_final_approval: true
      checkpoint_intervals: 3
    keyword_based:
      enabled: true
    interaction:
      timeout_seconds: 600
      timeout_default_action: "rejected"
  
  # 演示模式：中等审批
  demo:
    enabled: true
    risk_based:
      require_final_approval: true
      checkpoint_intervals: 5
    keyword_based:
      enabled: true
    interaction:
      timeout_seconds: 180
      timeout_default_action: "cancelled"
"""

# Python代码中的配置示例
def create_conservative_hitl():
    """创建保守的Human-in-the-Loop配置"""
    from src.agent.human_loop import (
        HumanLoopManager, RiskBasedApprovalStrategy, 
        KeywordApprovalStrategy, CLIInteractionHandler
    )
    
    # 严格的策略配置
    strategies = [
        RiskBasedApprovalStrategy(
            high_risk_tools=[
                "file_write", "file_delete", "system_command", 
                "execute_trade", "send_email", "database_write",
                "api_call_external"
            ],
            require_final_approval=True,
            checkpoint_intervals=3  # 每3轮检查一次
        ),
        KeywordApprovalStrategy(
            sensitive_keywords=[
                "删除", "清空", "格式化", "重置", "购买", "出售", 
                "转账", "支付", "投资", "交易", "买入", "卖出"
            ]
        )
    ]
    
    # 交互处理器
    interaction_handler = CLIInteractionHandler()
    
    return HumanLoopManager(interaction_handler, strategies)


def create_permissive_hitl():
    """创建宽松的Human-in-the-Loop配置"""
    from src.agent.human_loop import (
        HumanLoopManager, RiskBasedApprovalStrategy, CLIInteractionHandler
    )
    
    # 宽松的策略配置
    strategies = [
        RiskBasedApprovalStrategy(
            high_risk_tools=["system_command", "file_delete"],  # 只有最危险的操作
            require_final_approval=False,
            checkpoint_intervals=10  # 很少检查
        )
    ]
    
    interaction_handler = CLIInteractionHandler()
    
    return HumanLoopManager(interaction_handler, strategies)


def create_custom_approval_strategy():
    """创建自定义审批策略的示例"""
    from src.agent.human_loop import HumanApprovalStrategy, ApprovalType, ApprovalContext
    
    class CustomFinancialApprovalStrategy(HumanApprovalStrategy):
        """金融场景的自定义审批策略"""
        
        def should_request_approval(self, context: ApprovalContext) -> tuple[bool, ApprovalType, str]:
            # 1. 检查是否涉及金融交易
            if context.action and any(keyword in context.action.lower() for keyword in 
                                    ['trade', 'buy', 'sell', 'transfer', 'payment']):
                return True, ApprovalType.HIGH_RISK_ACTION, "涉及金融交易操作"
            
            # 2. 检查金额相关的参数
            if context.action_input:
                for key, value in context.action_input.items():
                    if key.lower() in ['amount', 'quantity', 'price'] and isinstance(value, (int, float)):
                        if value > 10000:  # 大额交易
                            return True, ApprovalType.HIGH_RISK_ACTION, f"涉及大额金融操作: {value}"
            
            # 3. 检查最终答案中是否包含投资建议
            if context.final_answer:
                advice_keywords = ['建议', '推荐', '应该买入', '应该卖出', '投资', '购买']
                if any(keyword in context.final_answer for keyword in advice_keywords):
                    return True, ApprovalType.FINAL_ANSWER, "最终答案包含投资建议"
            
            return False, ApprovalType.TOOL_EXECUTION, ""
    
    return CustomFinancialApprovalStrategy()


# 集成到现有系统的示例
async def setup_hitl_for_stock_analysis():
    """为股票分析设置Human-in-the-Loop"""
    from src.agent.human_loop import HumanLoopManager, CLIInteractionHandler
    
    # 组合多个策略
    strategies = [
        create_custom_approval_strategy(),  # 自定义金融策略
        # 可以添加更多策略
    ]
    
    interaction_handler = CLIInteractionHandler()
    hitl_manager = HumanLoopManager(interaction_handler, strategies)
    
    # 可以根据情况动态启用/禁用
    if is_production_environment():
        hitl_manager.enable()
    else:
        hitl_manager.disable()
    
    return hitl_manager


def is_production_environment():
    """检查是否为生产环境"""
    import os
    return os.getenv("ENVIRONMENT") == "production"


if __name__ == "__main__":
    print("Human-in-the-Loop 配置示例")
    print("=" * 50)
    print(human_loop_config_example)
