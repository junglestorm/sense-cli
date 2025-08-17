from datetime import datetime
from mcp.server.fastmcp import FastMCP
import logging

# 仅调整本模块与相关MCP模块的日志级别，避免影响全局 root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)

for name in ["mcp", "mcp.server", "mcp.server.fastmcp", "mcp.server.lowlevel"]:
    lg = logging.getLogger(name)
    lg.setLevel(logging.CRITICAL)
    lg.propagate = False

# Create server
mcp = FastMCP("Time Server")


@mcp.tool()
def get_time():
    """Get the current time"""
    return {"current_time": datetime.now().isoformat()}


if __name__ == "__main__":
    mcp.run()
