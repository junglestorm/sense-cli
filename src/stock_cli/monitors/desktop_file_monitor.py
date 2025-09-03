import os
import time
import asyncio
from typing import Dict, Any, Set
from ..core.monitor_manager import Monitor, get_monitor_manager
from ..core.rag import add_document_to_rag  # 假设rag.py中有此方法

# 桌面路径，跨平台支持

DESKTOP_PATH = os.path.expanduser('~/Desktop')
# 支持常见文本文件类型
SUPPORTED_EXTS = {
    '.txt', '.md', '.csv', '.log', '.json', '.yaml', '.yml', '.ini', '.conf', '.py', '.rst', '.xml', '.html', '.htm', '.bat', '.sh', '.js', '.css', '.ts', '.toml', '.cfg', '.tex', '.out', '.dat', '.properties', '.java', '.c', '.cpp', '.h', '.hpp', '.go', '.rb', '.pl', '.php', '.sql', '.r', '.jl', '.scala', '.swift', '.dart', '.asm', '.s', '.vb', '.ps1', '.lua', '.coffee', '.groovy', '.makefile', '.mk', '.dockerfile', '.env', '.gitignore', '.gitattributes', '.npmrc', '.editorconfig', '.vscode', '.ipynb', '.tsv', '.mdown', '.markdown', '.rtf', '.lst', '.lst', '.text', '.cfg', '.conf', '.ini', '.log', '.lst', '.out', '.properties', '.rc', '.tsv', '.bat', '.sh', '.zsh', '.fish', '.csh', '.tcsh', '.ksh', '.bash', '.profile', '.bashrc', '.zshrc', '.cshrc', '.tcshrc', '.kshrc', '.bash_profile', '.bash_logout', '.zlogin', '.zlogout', '.zprofile', '.zshenv', '.zshrc', '.inputrc', '.screenrc', '.tmux.conf', '.vimrc', '.emacs', '.nanorc', '.dircolors', '.wgetrc', '.curlrc', '.pypirc', '.condarc', '.pip', '.pylintrc', '.flake8', '.coveragerc', '.mypy.ini', '.editorconfig', '.envrc', '.tool-versions', '.prettierrc', '.eslintrc', '.babelrc', '.stylelintrc', '.commitlintrc', '.npmrc', '.yarnrc', '.pnpmfile', '.pre-commit-config', '.pre-commit-config.yaml', '.pre-commit-config.yml', '.prettierignore', '.eslintignore', '.dockerignore', '.npmignore', '.yarnignore', '.gcloudignore', '.bazelrc', '.bazelignore', '.buckconfig', '.buckversion', '.watchmanconfig', '.flowconfig', '.tern-config', '.tern-project', '.jshintrc', '.jshintignore', '.mocharc', '.mocharc.json', '.mocharc.js', '.mocharc.yaml', '.mocharc.yml', '.ava.config.js', '.ava.config.cjs', '.ava.config.mjs', '.ava.config.json', '.ava.config.ts', '.ava.config.coffee', '.ava.config.ls', '.ava.config.babel.js', '.ava.config.babel.cjs', '.ava.config.babel.mjs', '.ava.config.babel.json', '.ava.config.babel.ts', '.ava.config.babel.coffee', '.ava.config.babel.ls', '.ava.config.babel.babel.js', '.ava.config.babel.babel.cjs', '.ava.config.babel.babel.mjs', '.ava.config.babel.babel.json', '.ava.config.babel.babel.ts', '.ava.config.babel.babel.coffee', '.ava.config.babel.babel.ls', '.ava.config.babel.babel.babel.js', '.ava.config.babel.babel.babel.cjs', '.ava.config.babel.babel.babel.mjs', '.ava.config.babel.babel.babel.json', '.ava.config.babel.babel.babel.ts', '.ava.config.babel.babel.babel.coffee', '.ava.config.babel.babel.babel.ls', '.txt', '.md', '.csv', '.log', '.json', '.yaml', '.yml', '.ini', '.conf', '.py', '.rst', '.xml', '.html', '.htm', '.bat', '.sh', '.js', '.css', '.ts', '.toml', '.cfg', '.tex', '.out', '.dat', '.properties', '.java', '.c', '.cpp', '.h', '.hpp', '.go', '.rb', '.pl', '.php', '.sql', '.r', '.jl', '.scala', '.swift', '.dart', '.asm', '.s', '.vb', '.ps1', '.lua', '.coffee', '.groovy', '.makefile', '.mk', '.dockerfile', '.env', '.gitignore', '.gitattributes', '.npmrc', '.editorconfig', '.vscode', '.ipynb', '.tsv', '.mdown', '.markdown', '.rtf', '.lst', '.lst', '.text', '.cfg', '.conf', '.ini', '.log', '.lst', '.out', '.properties', '.rc', '.tsv', '.bat', '.sh', '.zsh', '.fish', '.csh', '.tcsh', '.ksh', '.bash', '.profile', '.bashrc', '.zshrc', '.cshrc', '.tcshrc', '.kshrc', '.bash_profile', '.bash_logout', '.zlogin', '.zlogout', '.zprofile', '.zshenv', '.zshrc', '.inputrc', '.screenrc', '.tmux.conf', '.vimrc', '.emacs', '.nanorc', '.dircolors', '.wgetrc', '.curlrc', '.pypirc', '.condarc', '.pip', '.pylintrc', '.flake8', '.coveragerc', '.mypy.ini', '.editorconfig', '.envrc', '.tool-versions', '.prettierrc', '.eslintrc', '.babelrc', '.stylelintrc', '.commitlintrc', '.npmrc', '.yarnrc', '.pnpmfile', '.pre-commit-config', '.pre-commit-config.yaml', '.pre-commit-config.yml', '.prettierignore', '.eslintignore', '.dockerignore', '.npmignore', '.yarnignore', '.gcloudignore', '.bazelrc', '.bazelignore', '.buckconfig', '.buckversion', '.watchmanconfig', '.flowconfig', '.tern-config', '.tern-project', '.jshintrc', '.jshintignore', '.mocharc', '.mocharc.json', '.mocharc.js', '.mocharc.yaml', '.mocharc.yml', '.ava.config.js', '.ava.config.cjs', '.ava.config.mjs', '.ava.config.json', '.ava.config.ts', '.ava.config.coffee', '.ava.config.ls', '.ava.config.babel.js', '.ava.config.babel.cjs', '.ava.config.babel.mjs', '.ava.config.babel.json', '.ava.config.babel.ts', '.ava.config.babel.coffee', '.ava.config.babel.ls', '.ava.config.babel.babel.js', '.ava.config.babel.babel.cjs', '.ava.config.babel.babel.mjs', '.ava.config.babel.babel.json', '.ava.config.babel.babel.ts', '.ava.config.babel.babel.coffee', '.ava.config.babel.babel.ls', '.ava.config.babel.babel.babel.js', '.ava.config.babel.babel.babel.cjs', '.ava.config.babel.babel.babel.mjs', '.ava.config.babel.babel.babel.json', '.ava.config.babel.babel.babel.ts', '.ava.config.babel.babel.babel.coffee', '.ava.config.babel.babel.babel.ls'
}
SCAN_INTERVAL = 10  # 秒

async def scan_desktop_files() -> Set[str]:
    """获取桌面目录下所有支持的文件路径集合"""
    files = set()
    for fname in os.listdir(DESKTOP_PATH):
        fpath = os.path.join(DESKTOP_PATH, fname)
        if os.path.isfile(fpath) and os.path.splitext(fname)[1].lower() in SUPPORTED_EXTS:
            files.add(fpath)
    return files

async def desktop_file_monitor(arguments: Dict[str, Any]):
    """监控桌面文件变化并自动添加新文件到RAG数据库"""
    known_files = await scan_desktop_files()
    while True:
        await asyncio.sleep(SCAN_INTERVAL)
        current_files = await scan_desktop_files()
        new_files = current_files - known_files
        for fpath in new_files:
            try:
                # 这里只处理文本文件，pdf等可扩展
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(4096)  # 只取前4K内容，可根据需要调整
                # 调用RAG接口添加文档
                await add_document_to_rag(fpath, content)
            except Exception as e:
                print(f"[桌面监控] 添加文件失败: {fpath}, 错误: {e}")
        known_files = current_files

async def register_desktop_file_monitor():
    manager = await get_monitor_manager()
    monitor = Monitor(
        name="desktop_file_monitor",
        description="监控桌面文件变化并自动添加到RAG数据库",
        parameters={},
        start_func=desktop_file_monitor
    )
    manager.register_monitor(monitor)
