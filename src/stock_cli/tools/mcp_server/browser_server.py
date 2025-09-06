import os
import logging
from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Any, Optional
import asyncio
from browser_history import get_history

logger = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)

for name in ["mcp", "mcp.server", "mcp.server.fastmcp", "mcp.server.lowlevel"]:
    lg = logging.getLogger(name)
    lg.setLevel(logging.CRITICAL)
    lg.propagate = False

mcp = FastMCP("Browser Server")

@mcp.tool()
async def get_browser_history() -> Dict[str, Any]:
    """获取浏览器历史记录"""
    try:
        outputs = get_history()
        history_items = []
        for item in outputs.histories:
            history_items.append({
                "url": item[1],
                "title": item[0],
                "timestamp": item[2].isoformat() if item[2] else None
            })
        return {"success":True, "data": history_items}
    except Exception as e:
        logger.error(f"获取浏览器历史记录失败: {str(e)}")
        return {"success":False, "error": str(e)}
    
@mcp.tool()
async def get_url_content(url: str) -> Dict[str, Any]:
    """
    获取指定URL的网页内容
    参数：
        url: 目标网页的URL
    """
    import httpx
    from bs4 import BeautifulSoup

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)
            return {"success":True, "url": url, "content": text_content}
    except Exception as e:
        logger.error(f"获取URL内容失败 ({url}): {str(e)}")
        return {"success":False, "url": url, "error": str(e)}
    
if __name__ == "__main__":
    mcp.run()