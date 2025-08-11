"""工具执行器

简单的工具调用模块，负责执行工具并返回结果
"""

import logging
from typing import Dict, Any, Optional, NamedTuple
from ..tools.mcp_server_manager import MCPServerManager

logger = logging.getLogger(__name__)


class ToolResult(NamedTuple):
    """工具执行结果"""

    success: bool
    result: Any
    error_message: Optional[str] = None


class ToolExecutor:
    """工具执行器 - 简单调用工具并返回结果"""

    def __init__(self):
        pass

    async def execute(self, action: str, action_input: Dict[str, Any]) -> ToolResult:
        """执行工具调用

        Args:
            action: 工具名称
            action_input: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        try:
            # 清理参数
            cleaned_params = action_input or {}

            # 执行工具调用
            mgr = await MCPServerManager.get_instance()
            result = await mgr.call_tool(action, cleaned_params)

            return ToolResult(success=True, result=result)

        except Exception as e:
            logger.warning(f"工具执行失败 {action}: {e}")
            return ToolResult(success=False, result=None, error_message=str(e))
