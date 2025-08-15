"""CLI会话管理器"""

from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory


class CLISessionManager:
    """CLI会话管理器"""
    
    def __init__(self, history_file: str = "data/history.txt"):
        # 确保历史文件目录存在
        history_path = Path(history_file)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建PromptSession实例以支持中文输入
        self.session = PromptSession(
            history=FileHistory(history_file),
            auto_suggest=AutoSuggestFromHistory(),
        )
        
    async def prompt_user(self, prompt_text: str = "> ") -> str:
        """提示用户输入"""
        try:
            user_input = await self.session.prompt_async(
                prompt_text,
                enable_history_search=True,
            )
            return user_input
        except (EOFError, KeyboardInterrupt):
            return ""