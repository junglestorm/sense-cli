from datetime import datetime
from mcp.server.fastmcp import FastMCP
import logging

# 禁用所有日志输出到控制台
logging.getLogger().setLevel(logging.CRITICAL)
for name in ["mcp", "mcp.server", "mcp.server.fastmcp", "mcp.server.lowlevel"]:
    logging.getLogger(name).setLevel(logging.CRITICAL)
    logging.getLogger(name).propagate = False

# Create server
mcp = FastMCP("Time Server")


@mcp.tool()
def get_time():
    """Get the current time"""
    return {"current_time": datetime.now().isoformat()}


if __name__ == "__main__":
    mcp.run()
