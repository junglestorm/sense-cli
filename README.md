# Multi-Agent CLI - 多智能体命令行交互平台

基于 ReAct 架构的多智能体协作平台，支持分布式会话、自动化触发和灵活角色注入。

## 快速开始

1. 安装依赖
   ```bash
   uv sync
   ```
2. 配置 LLM 密钥（编辑 config/settings.yaml）
3. 启动交互会话
   ```bash
   uv run stock-cli chat --role scientist --session-id scientist-session
   ```

## 核心用法

### 会话 (Session)
每个会话有唯一 session_id，历史自动持久化。
```bash
uv run stock-cli chat --session-id my-session
ls logs/sessions
```

### 角色 (Role)
通过 --role 参数注入角色，角色配置见 prompts/ 目录。
```bash
uv run stock-cli chat --role philosopher --session-id philosopher-session
```

### 触发器 (Trigger)
触发器是自动化任务，可通过 --trigger 参数启用。
```bash
uv run stock-cli chat --trigger session_inbox
```

## 多智能体协作

- 支持多会话、角色注入和自动化触发
- 基于 Redis 消息总线实现分布式发现与通信

示例：
```bash
uv run stock-cli chat --session-id agent1 --trigger session_inbox
uv run stock-cli chat --session-id agent2 --trigger session_inbox
```

## 交互命令

chat模式下支持 /exit、/role、/trigger 等斜杠命令，详见 /help。

## 扩展与开发

- 可扩展自定义触发器、角色和工具
- 项目结构：config/（配置）、src/stock_cli/（代码）、prompts/（角色）、data/（数据）

## 故障排除

- 智能体发现异常：清理 Redis 残留会话数据
- 触发器不工作：检查 Redis 服务和触发器名称
- 内存泄漏：定期清理会话文件，正常退出

## 核心概念

### 1. 会话 (Session)
会话是智能体的运行环境，每个会话有唯一的 session_id，用于持久化对话历史和状态。

**特性：**
- 会话上下文保存在 `logs/sessions/{session_id}.json`
- 同一 session_id 会共享并延续对话记忆
- 默认会话为 "default"

**会话管理命令：**
```bash
# 进入指定会话的交互聊天
uv run stock-cli --session-id agent-001

# 复用既有会话
uv run stock-cli chat --session-id agent-001

# 查看已有会话
ls logs/sessions

# 重置会话（删除历史记录）
rm logs/sessions/agent-001.json
```

### 2. 角色 (Role)
角色定义了智能体的行为模式和专业领域，通过YAML配置文件管理。你可以通过命令行参数 --role 在会话启动时动态注入角色。

**可用角色示例：**
- `philosopher` - 哲学家，擅长深度思考和哲学探讨
- `storyteller` - 故事讲述者，富有创造力和叙事能力
- `scientist` - 科学家，擅长用严密的逻辑和科学方法分析问题

**角色注入命令：**
```bash
# 启动指定角色的会话
uv run stock-cli chat --role scientist --session-id scientist-session

# 也可以随时切换角色
uv run stock-cli chat --role philosopher --session-id philosopher-session
```

**角色配置：**
角色配置文件位于 `prompts/` 目录，使用YAML格式定义系统提示词和行为模式。你也可以在 settings.yaml 的 roles 字段集中管理角色参数。

### 3. 触发器 (Trigger)
触发器是后台运行的自动化任务，可以监听事件并自动响应，实现智能体间的异步通信。你可以通过 --trigger 参数在 chat 命令中灵活启用。

**内置触发器：**
- `session_inbox` - 会话收件箱，监听其他会话的消息
- `ask_time` - 时间询问触发器，定时询问时间
- `crawler_event` - 爬虫事件触发器
- `custom_timer` - 自定义定时器

**触发器管理：**
```bash
# 启动时自动启用session_inbox触发器
uv run stock-cli chat --trigger session_inbox

# 启动多个触发器
uv run stock-cli chat --trigger session_inbox --trigger ask_time

# 在会话中管理触发器
/trigger list      # 查看触发器状态
/trigger start session_inbox  # 启动触发器
/trigger stop session_inbox   # 停止触发器
/trigger status    # 显示触发器详细状态
```

## 多智能体协作系统

### 架构概述
系统基于Redis消息总线实现分布式智能体发现和通信：
- **智能体注册**：会话启动时自动注册到Redis
- **动态发现**：所有智能体可以感知其他在线智能体
- **消息通信**：支持智能体间主动发送消息
- **被动触发**：通过session_inbox触发器监听和响应消息
- **角色注入**：通过 --role 参数和角色配置文件，灵活切换和注入不同角色行为

### 配置Redis（必需）
在 `config/settings.yaml` 中配置Redis：
```yaml
redis:
  host: "127.0.0.1"
  port: 6379
  db: 0
  password: ""
  prefix: "multi_agent"
```

### 协作流程示例

1. **启动多个智能体**：
```bash
# 终端1 - 启动research智能体
uv run stock-cli chat --session-id research --trigger session_inbox

# 终端2 - 启动analysis智能体  
uv run stock-cli chat --session-id analysis --trigger session_inbox

# 终端3 - 启动monitor智能体
uv run stock-cli chat --session-id monitor --trigger session_inbox
```

2. **发现在线智能体**：
在任一会话中询问："当前在线的智能体有哪些？"
系统会从Redis获取在线智能体列表并显示。

3. **发送消息**：
要求智能体向其他智能体发送消息，系统会输出通信XML：
```xml
<communication>
{"target":"research","message":"请分析最近的数据趋势"}
</communication>
```

4. **自动响应**：
目标智能体的session_inbox触发器会监听到消息，将其注入为用户输入并驱动智能体响应。

## 交互式命令系统

在chat模式下支持以下斜杠命令：

### 会话管理
- `/exit` - 退出当前会话
- `/clear` - 清空当前会话的屏幕
- `/session [id]` - 切换或显示当前会话ID


### 触发器管理
- `/trigger list` - 列出所有触发器状态
- `/trigger start <name>` - 启动指定触发器
- `/trigger stop <name>` - 停止指定触发器
- `/trigger status` - 显示触发器详细状态

### 系统信息
- `/help` - 显示帮助信息
- `/version` - 显示版本信息

## 高级功能

### 自定义触发器
您可以创建自定义触发器，在 `src/stock_cli/triggers/` 目录中添加新的触发器模块：

1. 创建触发器文件，如 `my_trigger.py`
2. 使用 `@register("trigger_name")` 装饰器注册触发器
3. 实现异步的触发器函数

### 智能体持久化
智能体数据自动保存到JSON文件，支持：
- 对话历史持久化
- 工具调用记录
- ReAct推理轨迹
- 自定义状态存储

### 性能优化
- 流式输出减少响应延迟
- 上下文裁剪防止token溢出
- 异步并发处理多个任务
- Redis缓存智能体发现信息

## 故障排除

### 常见问题

1. **智能体发现异常**：
   ```bash
   # 清理Redis中的残留会话数据
   redis-cli del "multi_agent:sessions"
   ```

2. **触发器不工作**：
   - 检查Redis服务器是否运行：`redis-cli ping`
   - 确认触发器名称正确

3. **内存泄漏**：
   - 定期清理旧的会话文件
   - 使用 `/exit` 正常退出会话

### 调试模式
```bash
# 启用调试日志
uv run stock-cli --debug chat

# 仅控制台日志
uv run stock-cli --log-console chat
```

## 开发指南

### 项目结构
```
multi-agent-cli/
├── config/                 # 配置文件
│   ├── settings.yaml      # 主配置
│   └── settings.example.yaml
├── src/stock_cli/         # 源代码
│   ├── commands/          # CLI命令
│   ├── core/              # 核心逻辑
│   ├── triggers/          # 触发器模块
│   └── tools/             # 工具函数
├── prompts/               # 角色提示词
└── data/                  # 数据存储
```

### 扩展功能
- 添加新工具：在 `src/stock_cli/tools/` 中实现
- 创建新角色：在 `prompts/` 中添加YAML文件
- 开发新触发器：在 `src/stock_cli/triggers/` 中注册

---
多智能体协作平台，支持分布式通信和自动化任务处理。
