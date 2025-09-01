
# MCP 多智能体自动化平台

本平台是一个支持自动化触发、多会话上下文、多智能体协作的命令行智能体系统。

## 🚀 快速开始

### 1. 安装依赖
```bash
uv sync
```

### 2. 配置环境
复制示例配置文件并编辑：
```bash
cp config/settings.example.yaml config/settings.yaml
```

编辑 `config/settings.yaml` 配置LLM和Redis：
```yaml
llm:
  provider: "openai"  # 或 deepseek, ollama
  api_key: "your-api-key"
  model: "gpt-4o-mini"

redis:
  host: "127.0.0.1"
  port: 6379
```

### 3. 启动Redis
```bash
redis-server
```

### 4. 使用命令
```bash
# 交互式聊天
uv run stock-cli chat --session-id my_session

# 查看可用工具
uv run stock-cli tools

# 查看活动角色会话
uv run stock-cli role list
```

## 📋 核心功能

### 角色系统
角色配置文件位于 `config/roles/`，支持自定义角色：
```yaml
name: technical_analyst
description: 技术分析师
system_prompt: 你是一名技术分析师，专注于股票技术指标分析...
allowed_mcp_servers: [stock_insight, market_context]
```

### MCP工具
- **stock_insight** - 股票技术指标和价格数据
- **market_context** - 市场整体情况和行业动态
- **fundamental_data** - 财务报表和基本面指标
- **sector_dynamics** - 行业板块表现分析

### 会话管理
支持多会话并行，会话历史自动持久化。

## 🔧 配置文件

主配置 `config/settings.yaml`：
```yaml
llm:
  provider: "openai"
  api_key: "sk-..."
  model: "gpt-4o-mini"

redis:
  host: "127.0.0.1"
  port: 6379
  db: 0

session:
  persist: true
  max_history: 50
```

## 💡 提示
使用 `uv run stock-cli --help` 查看所有可用命令和选项。
