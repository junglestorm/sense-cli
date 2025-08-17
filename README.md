# Stock CLI - 股票分析命令行工具

基于 ReAct 架构的股票分析命令行工具。

## 快速开始

### 1. 安装依赖
```bash
uv sync
```

### 2. 配置 DeepSeek API
```bash
# 复制配置文件
cp config/settings.example.yaml config/settings.yaml
# 编辑配置文件，添加你的 DeepSeek API 密钥
nano config/settings.yaml
```

配置示例：
```yaml
llm:
  deepseek:
    api_key: "your-deepseek-api-key"
    base_url: "https://api.deepseek.com/v1"
    model: "deepseek-chat"
```

### 3. 使用
```bash
# 单次问答
uv run stock-cli ask "分析一下大盘情况"

# 持续对话
uv run stock-cli chat

# 简化输出
uv run stock-cli chat --minimal
```

## 会话与如何重新进入 session

Stock CLI 以会话（session）为单位持久化上下文，同一 session_id 会共享并延续对话记忆。默认会话为 "default"。

- 全局入口直接进入指定会话（进入交互聊天）：
  ```bash
  uv run stock-cli --session-id research-001
  ```

- 进入聊天模式并复用既有会话：
  ```bash
  uv run stock-cli chat --session-id research-001
  ```

- 在单轮问答中复用会话（问答也会将内容记录到该会话的上下文中）：
  ```bash
  uv run stock-cli ask "分析一下大盘情况" --session-id research-001
  ```

- 查看已有会话文件（一个 session 对应一个持久化文件）：
  ```bash
  ls logs/sessions
  # 会看到类似：default.json、research-001.json ...
  ```

- 会话数据位置与重置方式：
  - 会话上下文保存在：logs/sessions/{session_id}.json
  - 若需重置某个会话的上下文，可删除对应的 JSON 文件（删除前请确认不再需要历史记录）：
    ```bash
    rm logs/sessions/research-001.json
    ```

提示：
- 使用相同的 --session-id 重复进入，即可“重新进入”对应会话并延续之前的上下文与记忆。
- 你也可以结合调试日志开关在控制台查看调试输出：
  ```bash
  uv run stock-cli --debug --session-id research-001
  ```
  或在当前日志级别下仅打开控制台日志：
  ```bash
  uv run stock-cli --log-console chat --session-id research-001
  ```

## 项目结构
```
stock-cli/
├── config/settings.yaml       # 配置文件
├── src/stock_cli/             # 源代码
├── prompts/                   # 提示词模板
└── data/                      # 数据存储
```

---
仅用于学习研究，不构成投资建议。
