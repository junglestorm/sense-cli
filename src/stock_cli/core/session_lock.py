import asyncio
from typing import Dict

_session_locks: Dict[str, asyncio.Lock] = {}

def get_session_lock(session_id: str) -> asyncio.Lock:
    """获取与会话ID关联的异步锁"""
    if session_id not in _session_locks:
        _session_locks[session_id] = asyncio.Lock()
    return _session_locks[session_id]
