"""
管理触发器
"""
from datetime import datetime
from mcp.server.fastmcp import FastMCP
from typing import List
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)

for name in ["mcp", "mcp.server", "mcp.server.fastmcp", "mcp.server.lowlevel"]:
    lg = logging.getLogger(name)
    lg.setLevel(logging.CRITICAL)
    lg.propagate = False

# Create server
mcp = FastMCP("trigger manager")

@mcp.tool()
def list_all_triggers():
    """列出所有可用的触发器"""
    pass

@mcp.tool()
def list__all_active_triggers():
    """列出所有已激活的触发器"""
    pass

@mcp.tool()
def activate_trigger(trigger_names: List[str], params:List[dict]):
    """激活指定的触发器"""
    pass

@mcp.tool()
def stop_trigger(trigger_name: List[str]):
    """停止指定的触发器"""
    pass