"""版本命令"""

from rich.console import Console

__version__ = "1.1.0"


def version():
    """显示版本信息"""
    console = Console()
    console.print(f"Stock Agent CLI v{__version__}")
    console.print("AI-Powered Stock Analysis Tool powered by ReAct Architecture")