
# sense-cli · 主动感知与监控驱动的智能体平台

**sense-cli** 是一个以“监控器驱动”为核心、支持自动化触发、多会话上下文的命令行多智能体平台。它强调主动感知、环境理解和用户行为洞察。

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
uv run sense-cli chat --session-id my_session

# 使用特定角色进行交互式聊天
uv run sense-cli chat --session-id my_session --role assistant

# 查看可用工具
uv run sense-cli tools

# 查看活动角色会话
uv run sense-cli role list
```

## 📋 核心功能




### 监控器系统与多智能体交互


平台内置“监控器”系统，支持多种自动化感知与触发：

- 支持循环定时、定点定时、桌面/文件/消息等多种监控器
- 所有监控器均可动态启动/停止，异步执行
- 基于 Redis 消息总线，支持跨会话、跨角色通信
- 智能体可主动感知环境变化，自动归档、分析、响应

监控器机制让平台具备高度自动化、主动感知和分布式智能体能力。

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
使用 `uv run sense-cli --help` 查看所有可用命令和选项。