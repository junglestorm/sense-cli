# Human-in-the-Loop 系统设计文档

## 🎯 核心概念

Human-in-the-Loop (HITL) 是在AI系统的自动化流程中，在关键决策点引入人工审批和干预机制，确保：

1. **安全性**: 防止AI执行高风险或破坏性操作
2. **可控性**: 人类可以随时介入并修正AI的行为
3. **透明性**: 所有关键决策都经过人类审查
4. **学习性**: 通过人类反馈改进AI决策质量

## 🏗️ 架构设计

### 1. 干预触发点

```
ReAct循环中的HITL触发点:
┌─────────────────────────────────────────────────────────────┐
│                     ReAct 执行流程                          │
├─────────────────────────────────────────────────────────────┤
│ 1. Thought (思考)                                           │
│    └─> [检查点] 迭代间隔检查                                │
│                                                             │
│ 2. Action (工具执行)                                        │
│    └─> [审批点] 高风险工具审批                              │
│    └─> [审批点] 敏感关键词检测                              │
│                                                             │
│ 3. Observation (观察结果)                                   │
│    └─> [检查点] 执行结果评估                                │
│                                                             │
│ 4. Final Answer (最终答案)                                  │
│    └─> [审批点] 最终答案确认                                │
└─────────────────────────────────────────────────────────────┘
```

### 2. 审批策略层次

```python
# 1. 基于风险的审批策略
class RiskBasedApprovalStrategy:
    - 高风险工具识别 (如: execute_trade, send_email, file_write)
    - 迭代检查点 (每N轮强制审批)
    - 最终答案确认

# 2. 基于关键词的审批策略  
class KeywordApprovalStrategy:
    - 敏感词汇检测 (如: 删除, 购买, 转账)
    - 动态风险评估

# 3. 自定义审批策略
class CustomApprovalStrategy:
    - 用户定义的审批规则
    - 领域特定的安全检查
```

### 3. 交互处理层

```python
# CLI 命令行交互
class CLIInteractionHandler:
    - 显示审批请求面板
    - 收集用户决策 (批准/拒绝/修改/取消)
    - 超时处理机制

# Web 界面交互 (扩展点)
class WebInteractionHandler:
    - HTTP API 审批接口
    - 异步通知机制
    - 多用户协作审批

# API 接口交互 (扩展点)
class APIInteractionHandler:
    - REST API 调用外部审批系统
    - 工作流集成
```

## 🔄 工作流程

### 典型审批流程

1. **触发检查**: AI在执行关键操作前检查是否需要审批
2. **审批请求**: 系统暂停执行，向人类发送审批请求
3. **人工决策**: 人类审查上下文信息，做出决策
4. **执行分支**:
   - ✅ **批准**: 继续原计划执行
   - ❌ **拒绝**: 跳过当前操作，AI重新思考
   - ✏️ **修改**: 使用人类修改后的参数执行
   - 🚫 **取消**: 终止整个任务

### 实际交互示例

```bash
🤔 需要人工审批
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
审批类型: high_risk_action
消息: 高风险工具: execute_trade

工具: execute_trade
参数: {"symbol": "AAPL", "quantity": 1000, "side": "buy"}
思考: 基于分析，建议买入苹果股票1000股

选择: yes, no, modify, cancel
> n

🔄 工具执行被拒绝 - 用户拒绝
Agent继续重新思考...
```

## 🎛️ 配置选项

### 1. 启用方式

```bash
# 启用基本HITL (工具审批)
python main.py ask "分析苹果股票" --human-approval

# 启用完整HITL (包括最终答案审批)
python main.py chat --human-approval --require-final-approval

# 自定义高风险工具
python main.py ask "查询数据" --human-approval --high-risk-tools execute_trade,send_email

# 设置检查点间隔
python main.py chat --human-approval --checkpoint-interval 3
```

### 2. 策略配置

```python
# 在代码中配置
human_loop_manager = create_default_human_loop(
    console=console,
    high_risk_tools=["execute_trade", "file_write", "send_email"],
    require_final_approval=True
)

# 或使用自定义策略
from src.agent.human_loop import RiskBasedApprovalStrategy, KeywordApprovalStrategy

strategies = [
    RiskBasedApprovalStrategy(
        high_risk_tools=["execute_trade", "delete_file"],
        checkpoint_intervals=5,
        require_final_approval=True
    ),
    KeywordApprovalStrategy(
        sensitive_keywords=["删除", "购买", "出售", "转账", "清空"]
    )
]
```

## 🛡️ 安全特性

### 1. 超时保护
- 默认5分钟审批超时
- 超时自动拒绝操作
- 可配置的超时策略

### 2. 操作记录
- 完整的审批决策日志
- 人机交互轨迹记录
- 可审计的决策历史

### 3. 多层防护
- 策略层: 多重审批策略并行检查
- 工具层: 高风险工具强制拦截
- 内容层: 敏感词汇实时监控

## 🚀 使用场景

### 1. 金融交易场景
```python
# 股票交易需要人工确认
high_risk_tools = [
    "execute_trade",      # 执行交易
    "cancel_order",       # 取消订单
    "modify_position"     # 修改持仓
]
```

### 2. 数据操作场景
```python
# 数据库操作需要审批
high_risk_tools = [
    "delete_records",     # 删除记录
    "update_schema",      # 更新架构
    "backup_restore"      # 备份恢复
]
```

### 3. 外部通信场景
```python
# 外部通信需要审批
high_risk_tools = [
    "send_email",         # 发送邮件
    "post_social_media",  # 社交媒体发布
    "api_call_external"   # 外部API调用
]
```

## 🔧 扩展机制

### 1. 自定义审批策略

```python
from src.agent.human_loop import HumanApprovalStrategy, ApprovalType

class MyCustomStrategy(HumanApprovalStrategy):
    def should_request_approval(self, context):
        # 自定义审批逻辑
        if self.is_weekend() and context.action == "execute_trade":
            return True, ApprovalType.HIGH_RISK_ACTION, "周末交易需要审批"
        return False, ApprovalType.TOOL_EXECUTION, ""
```

### 2. 自定义交互处理器

```python
from src.agent.human_loop import InteractionHandler

class SlackInteractionHandler(InteractionHandler):
    async def request_approval(self, request):
        # 通过Slack发送审批请求
        response = await self.send_slack_message(request)
        return self.parse_slack_response(response)
```

### 3. 集成外部审批系统

```python
class WorkflowInteractionHandler(InteractionHandler):
    async def request_approval(self, request):
        # 集成企业工作流审批系统
        workflow_id = await self.create_workflow_request(request)
        return await self.wait_for_workflow_approval(workflow_id)
```

## 📈 监控与分析

### 1. 审批统计
- 审批请求频率
- 批准/拒绝比率
- 平均审批时间
- 高风险操作分析

### 2. 性能影响
- HITL对执行速度的影响
- 人工干预成本分析
- 自动化率vs安全性平衡

### 3. 质量改进
- 基于人工反馈的策略优化
- 误报/漏报分析
- 审批策略迭代改进

## 🎯 最佳实践

### 1. 策略配置
- 根据业务场景配置合适的触发策略
- 避免过度审批导致效率低下
- 定期评估和调整审批规则

### 2. 用户体验
- 提供清晰的审批界面
- 包含足够的上下文信息
- 支持快速决策的快捷操作

### 3. 安全考虑
- 高风险操作必须经过审批
- 建立操作白名单和黑名单
- 实现多级审批机制

---

## 总结

我设计的Human-in-the-Loop系统是一个**多层次、可配置、安全优先**的人机协作框架。它不是简单的"询问用户是否继续"，而是一个完整的**智能审批决策系统**，能够：

1. **智能识别**需要人工干预的关键节点
2. **灵活配置**不同场景下的审批策略  
3. **优雅处理**人机交互和决策分支
4. **完整记录**审批过程和决策轨迹
5. **持续优化**基于反馈的策略改进

这个系统让AI Agent在保持高度自动化的同时，确保人类始终掌握最终控制权，实现了**安全性与效率的平衡**。
