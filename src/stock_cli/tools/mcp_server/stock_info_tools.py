"""
股票信息相关工具模块：包含与股票信息、概念板块等相关的功能工具。
"""

import logging
from datetime import datetime
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("Stock Info Tools Server")

@mcp.tool()
def stock_main_business(symbol: str) -> Dict[str, Any]:
    """
    获取股票的主营介绍数据。

    参数：
        symbol (str): 股票代码，例如“000066”。

    返回：
        dict: 包含成功状态和主营介绍数据。
    """
    import akshare as ak
    try:
        data = ak.stock_zyjs_ths(symbol=symbol)
        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_main_business error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_hot_keyword(symbol: str) -> Dict[str, Any]:
    """
    获取指定股票代码的热门关键词数据。

    参数：
        symbol (str): 股票代码，例如“SZ000665”。

    返回：
        dict: 包含成功状态和热门关键词数据。
    """
    import akshare as ak
    try:
        data = ak.stock_hot_keyword_em(symbol=symbol)
        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_hot_keyword error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_bid_ask(symbol: str) -> Dict[str, Any]:
    """
    获取指定股票的行情报价数据。

    参数：
        symbol (str): 股票代码，例如“000001”。

    返回：
        dict: 包含成功状态和行情报价数据。
    """
    import akshare as ak
    try:
        data = ak.stock_bid_ask_em(symbol=symbol)
        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_bid_ask error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_board_concept_info(symbol: str) -> Dict[str, Any]:
    """
    获取同花顺概念板块简介数据。

    参数：
        symbol (str): 概念名称，例如“阿里巴巴概念”。

    返回：
        dict: 包含成功状态和概念板块简介数据。
    """
    import akshare as ak
    try:
        data = ak.stock_board_concept_info_ths(symbol=symbol)
        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_board_concept_info error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_board_concept_name() -> Dict[str, Any]:
    """
    获取东方财富网概念板块的实时行情数据。

    返回：
        dict: 包含成功状态和概念板块实时行情数据。
    """
    import akshare as ak
    try:
        data = ak.stock_board_concept_name_em()
        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_board_concept_name error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_board_concept_cons(symbol: str) -> Dict[str, Any]:
    """
    获取东方财富网概念板块的成份股数据，并返回前10只股票的具体数据。

    参数：
        symbol (str): 概念板块名称或代码，例如“融资融券”或“BK0655”。

    返回：
        dict: 包含成功状态和前10只成份股数据。
    """
    import akshare as ak
    try:
        data = ak.stock_board_concept_cons_em(symbol=symbol)
        top_10 = data.head(10)
        return {
            "success": True,
            "data": top_10.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_board_concept_cons error: {e}")
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    mcp.run()