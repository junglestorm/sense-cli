"""显示工具"""

from typing import List

from rich import print
from rich.panel import Panel
from rich.console import Console
from pyfiglet import Figlet


def show_logo():
    """显示专业风格的logo"""
    console = Console()
    f = Figlet(font="slant", width=120)
    logo_text = f.renderText("Stock Agent CLI")
    console.print(f"[bold blue]{logo_text}[/bold blue]")
    console.print(
        "[green]AI-Powered Stock Analysis Tool powered by ReAct Architecture[/green]\n"
    )


def show_help():
    """显示帮助信息"""
    from ..cli import __version__
    console = Console()
    help_text = f"""
[bold blue]Stock Agent CLI v{__version__} - 帮助[/bold blue]

[yellow]基本用法:[/yellow]
  直接输入问题与AI对话，所有模式都会显示AI的思考过程

[yellow]中断功能:[/yellow]
  在任何模式下，当 AI 正在思考或生成答案时：
  • 按 Ctrl+C 可以中断当前任务
  • 中断后可以立即输入新的问题
  
[yellow]特殊命令:[/yellow]
  /help, /h      - 显示此帮助信息
  /tools         - 列出可用工具
  /status        - 显示系统状态
  /clear         - 清屏
  /reset         - 清空会话记忆
  /version       - 显示版本信息
  /quit, /exit   - 退出程序

[yellow]示例问题:[/yellow]
  分析一下阿里巴巴的股价走势
  帮我查找最近的股市新闻
  比较一下腾讯和阿里巴巴的财务数据

[yellow]命令行选项:[/yellow]
  --help         - 显示命令帮助
  --version, -V  - 显示版本信息
  --debug, -d    - 显示调试信息
  --no-color     - 禁用彩色输出
"""
    console.print(help_text.strip())


def show_status():
    """显示系统状态"""
    from ..agent.runtime import current_model
    console = Console()
    try:
        model = current_model()
        status = "Active" if model else "Check configuration"
        model_name = model or "Check configuration"

        status_text = f"""
Status: {status}
Model: {model_name}
Services: Running
"""
        console.print(status_text.strip())
    except Exception:
        console.print("Status: Unable to determine")


def format_reasoning(lines: List[str]) -> List[str]:
    """格式化推理过程"""
    out: List[str] = []
    for ln in lines:
        if ln.startswith("[Agent]"):
            out.append(f"[cyan]> {ln.replace('[Agent]', '').strip()}[/cyan]")
        elif ln.startswith("[ReAct]"):
            core = ln.replace("[ReAct]", "").strip()
            out.append(f"[dim]• {core}[/dim]")
    return out


def print_banner(model: str, mode: str):
    """打印横幅"""
    console = Console()
    # 仅在 verbose 模式调用
    line = f"model={model} mode={mode}"
    console.print(f"[dim]{line}[/dim]")