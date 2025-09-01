"""会话收件箱触发器（已废弃）

此文件已废弃，请使用 monitors/session_inbox.py 中的监控器实现。
"""

import logging

logger = logging.getLogger(__name__)

# 空的触发器函数，仅用于向后兼容
@register("session_inbox")
async def session_inbox_trigger(*args, **kwargs):
    logger.warning("会话收件箱触发器已废弃，请使用会话收件箱监控器")
    return None