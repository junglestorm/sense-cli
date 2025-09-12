import logging
from typing import Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient

from stock_cli.core.config_resolver import resolve_settings_path, load_settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)

mcp = FastMCP("Web Search Server")

def _get_tavily_client() -> Optional[TavilyClient]:
    """获取 Tavily 客户端实例"""
    try:
        settings_path = resolve_settings_path()
        config = load_settings(settings_path)
        api_key = config.get("tavily_api_key")
        
        if not api_key:
            logger.error("Tavily API key not found in config")
            return None
            
        return TavilyClient(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize Tavily client: {e}")
        return None

@mcp.tool()
async def search_web(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    使用 Tavily 搜索网页内容
    
    Args:
        query: 搜索查询词
        max_results: 最大结果数量，默认5
        search_depth: 搜索深度，可选 "basic" 或 "advanced"
        include_domains: 包含的域名列表
        exclude_domains: 排除的域名列表
    
    Returns:
        包含搜索结果的字典
    """
    try:
        client = _get_tavily_client()
        if not client:
            return {
                "success": False,
                "error": "Tavily client initialization failed"
            }
        
        # 构建搜索参数
        search_params = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth
        }
        
        if include_domains:
            search_params["include_domains"] = include_domains
        if exclude_domains:
            search_params["exclude_domains"] = exclude_domains
        
        # 执行搜索
        response = client.search(**search_params)
        
        # 处理结果
        results = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0),
                "published_date": item.get("published_date", "")
            })
        
        return {
            "success": True,
            "query": query,
            "results": results,
            "total_results": len(results)
        }
        
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        return {
            "success": False,
            "query": query,
            "error": str(e)
        }

if __name__ == "__main__":
    mcp.run()