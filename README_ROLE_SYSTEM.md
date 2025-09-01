# 角色配置系统使用指南

## 概述


## 角色配置文件格式

### 基本结构
```yaml
name: "角色名称"
description: "角色描述"
system_prompt: |
  系统提示词内容...
allowed_mcp_servers:
  - "server_name1"
  - "server_name2"
permissions:
  max_iterations: 10
  timeout: 300
  enable_communication: true
```

### 配置字段说明

- **name**: 角色名称（唯一标识）
- **description**: 角色描述信息
- **system_prompt**: 系统提示词，定义角色的行为和能力
- **allowed_mcp_servers**: 允许使用的MCP服务器列表
- **permissions**: 权限配置
  - max_iterations: 最大迭代次数
  - timeout: 超时时间（秒）
  - enable_communication: 是否启用会话通信

## 可用命令

### 查看所有角色
```bash
python -m stock_cli role list
```

### 查看角色详情
```bash
python -m stock_cli role show <角色名称>
```

### 验证角色配置
```bash
python -m stock_cli role validate
```

### 使用指定角色启动聊天
```bash
python -m stock_cli chat --role technical_analyst
python -m stock_cli chat --role fundamental_analyst
```

## 预定义角色示例

### 技术分析师 (technical_analyst)
- **专注领域**: 技术指标分析
- **可用工具**: stock_insight, market_context
- **特点**: 擅长趋势识别、支撑阻力位分析

### 基本面分析师 (fundamental_analyst)  
- **专注领域**: 财务数据分析
- **可用工具**: fundamental_data, market_context, stock_pool
- **特点**: 擅长财务指标分析、估值评估

## 配置验证

系统会自动验证：
1. MCP服务器名称是否在 `config/mcp_config.json` 中存在
3. 配置文件格式是否正确

## 扩展自定义角色

### 1. 创建新的角色配置文件
在 `config/roles/` 目录下创建新的YAML文件，例如 `quant_analyst.yaml`

### 2. 配置角色能力
```yaml
name: "量化分析师"
description: "专注于量化交易策略分析"
system_prompt: |
  你是一名量化分析师，专注于...
allowed_mcp_servers:
  - "stock_insight"
  - "market_context" 
  - "sector_dynamics"
  - "ask_time"
permissions:
  max_iterations: 15
  timeout: 600
```

### 3. 验证配置
```bash
python -m stock_cli role validate
```

### 4. 使用新角色
```bash
python -m stock_cli chat --role quant_analyst
```

## 架构优势

1. **完全解耦**: 角色配置与核心代码分离
2. **动态加载**: 无需重启即可加载新角色
4. **易于扩展**: 通过配置文件即可添加新角色
5. **验证机制**: 自动验证配置的有效性

## 故障排除

### 常见问题

1. **角色未找到**: 检查配置文件是否在 `config/roles/` 目录
2. **MCP服务器不存在**: 检查 `config/mcp_config.json` 中的服务器名称

### 调试命令
```bash
# 查看所有可用MCP服务器
python -c "from src.stock_cli.tools.mcp_server_manager import MCPServerManager; import asyncio; mgr = MCPServerManager(); mgr._load_config(); print([s.name for s in mgr.servers_config])"

```

## 最佳实践

1. **角色命名**: 使用英文小写和下划线，如 `quant_researcher`
2. **提示词设计**: 明确角色职责和使用工具的策略
3. **权限设置**: 根据角色需求合理设置迭代次数和超时时间
4. **版本控制**: 将角色配置文件纳入版本控制