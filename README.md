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

## 多 Session 分布式协作（动态发现 + 主动通信 + 被动触发）

本项目已支持在分布式/多终端环境中的多 session（多 agent）协作能力，包括：
- 动态注册与发现：会话启动自动“上线”、退出自动“下线”，其它会话可在推理时感知在线列表（active_sessions）。
- 主动通信：模型可输出 XML 同级标签 &lt;communication&gt;{"target":"session_id","message":"..."}&lt;/communication&gt; 主动向目标会话发送消息。
- 被动触发：被动会话通过“会话收件箱”触发器监听消息，收到后将其注入对话并驱动响应。
- chat 与 trigger 兼容：chat 启动会自动注册在线并后台监听收件箱；也支持通过 --trigger/--triggers 载入触发器配置。

### 配置示例

1) 在 config/settings.yaml（可参考 settings.example.yaml）中可选配置“消息总线”（默认本地 Redis）：
```yaml
redis:
  host: "127.0.0.1"
  port: 6379
  db: 0
  password: ""
  prefix: "stock_cli"
```

2) 在触发器文件（例如 ./config/triggers.yaml）启用“会话收件箱”：
```yaml
triggers:
  - name: "session-inbox"
    type: "session_inbox"
    enabled: true
    params: {}
```

### 运行与验证流程

在两个终端中执行以下命令进行验证：

- 启动被动会话（如 sam），加载触发器配置以开启“会话收件箱”：
```bash
uv run stock-cli trigger --session-id sam --trigger ./config/triggers.yaml
```

- 启动 chat 会话（如 bill），同样加载触发器配置（chat 也会注册为在线并后台监听）：
```bash
uv run stock-cli chat --session-id bill --trigger ./config/triggers.yaml
```

在 bill 的 chat 终端中：
- 询问“当前可通信的会话有哪些”，模型会从 active_sessions 感知在线列表（应包含 sam）。
- 要求其向 sam 发包，模型可输出如下通信 XML（与 &lt;action&gt; 同级）：
```xml
<communication>
{"target":"sam","message":"你好，我是bill，会话间协作请求：请拉取最近的K线简报并回传。"}
</communication>
```
- 系统会自动将消息发送至 sam 的收件箱，sam 监听到消息后会将其注入为用户消息，并驱动模型进行响应。
---
仅用于学习研究，不构成投资建议。（目前所有的金融接口工具都未进行实验与测试，请勿使用，询问也不会获得正确结果。）
