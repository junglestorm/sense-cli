"""
特殊股票池工具：提供涨停、炸板、强势、跌停等事件池查询。
"""

import logging
from datetime import datetime
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("Stock Pool Tools")


@mcp.tool()
def get_zt_pool(date: str) -> Dict[str, Any]:
    """
    获取指定日期的涨停股池。
    """
    import akshare as ak
    try:
        df = ak.stock_zt_pool_em(date=date)
        return {
            "success": True,
            "data": df.to_dict(orient="records"),
            "count": len(df),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"get_zt_pool error: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def get_strong_pool(date: str) -> Dict[str, Any]:
    """
    获取强势股池（突破、高量比、新高）。
    """
    import akshare as ak
    try:
        df = ak.stock_zt_pool_strong_em(date=date)
        return {
            "success": True,
            "data": df.to_dict(orient="records"),
            "count": len(df),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"get_strong_pool error: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def get_zb_pool(date: str) -> Dict[str, Any]:
    """
    获取炸板股池（曾涨停但打开）。
    """
    import akshare as ak
    try:
        df = ak.stock_zt_pool_zbgc_em(date=date)
        return {
            "success": True,
            "data": df.to_dict(orient="records"),
            "count": len(df),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"get_zb_pool error: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def get_dt_pool(date: str) -> Dict[str, Any]:
    """
    获取跌停股池。
    """
    import akshare as ak
    try:
        df = ak.stock_zt_pool_dtgc_em(date=date)
        return {
            "success": True,
            "data": df.to_dict(orient="records"),
            "count": len(df),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"get_dt_pool error: {e}")
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    mcp.run()