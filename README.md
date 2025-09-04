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

### 4 启动ollama
```bash
ollama pull nomic-embed-text
```

### 5. 使用命令
```bash
# 交互式聊天
uv run stock-cli chat --session-id my_session

# 使用特定角色进行交互式聊天
uv run stock-cli chat --session-id my_session --role assistant

# 查看可用工具
uv run stock-cli tools

# 查看活动角色会话
uv run stock-cli role list
```

## 📋 核心功能




### 监控器系统与多智能体交互

平台内置监控器系统，实现自动化任务与多智能体协作：

- 支持循环定时、定点定时、会话消息监听等多种监控器
- 所有监控器均可动态启动/停止，异步执行
- 基于 Redis 消息总线，支持跨会话、跨角色通信
- 多角色可通过消息互发、协作，构建复杂自动化流程

支持通过自然语言指令为会话开启桌面监控器，自动将桌面文档转化为 RAG 数据库，并持续监控桌面文档的变化，实现文档的实时同步与智能检索。

监控器和多智能体机制让平台具备高度自动化和分布式智能体协作能力。

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