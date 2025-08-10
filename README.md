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
