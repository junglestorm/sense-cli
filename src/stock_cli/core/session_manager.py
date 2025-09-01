"""会话管理器，支持会话统一管理和监控器机制"""

import asyncio
import logging
from typing import Dict, Any, Optional, List

from .session import SessionManager as BaseSessionManager

logger = logging.getLogger(__name__)


class SessionManager:
    """扩展的会话管理器"""
    def __init__(self):
        self._base_manager = BaseSessionManager()
    def get_session(self, session_id: str) -> Any:
        """获取会话实例"""
        return self._base_manager.get_session(session_id)