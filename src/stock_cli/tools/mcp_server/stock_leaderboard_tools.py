"""
股票信息相关工具模块：包含与股票信息、概念板块等相关的功能工具。
"""

import logging
from datetime import datetime
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("股票信息工具服务：提供与股票龙虎榜、概念板块等相关的多种查询和分析功能。支持获取个股龙虎榜详情、营业部排行、每日龙虎榜详情、个股上榜统计、营业上榜统计以及机构席位成交明细等数据。")

@mcp.tool()
def stock_lhb_stock_detail_em(symbol: str, date: str, flag: str) -> Dict[str, Any]:
    """
    获取个股龙虎榜详情。

    参数：
        symbol (str): 股票代码，例如 "600077"。
        date (str): 日期，例如 "20220310"。
        flag (str): 买入或卖出，"买入" 或 "卖出"。

    返回：
        dict: 包含成功状态和龙虎榜详情数据。
    """
    import akshare as ak
    try:
        data = ak.stock_lhb_stock_detail_em(symbol=symbol, date=date, flag=flag)
        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_lhb_stock_detail_em error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_lh_yyb_most_sorted() -> Dict[str, Any]:
    """
    获取龙虎榜-营业部排行-上榜次数最多的数据，并按照年内3日跟买成功率、合计动用资金、年内上榜次数排序后分别返回前10。

    返回：
        dict: 包含成功状态和排序后的营业部排行数据。
    """
    import akshare as ak
    try:
        data = ak.stock_lh_yyb_most()
        if data.empty:
            return {"success": False, "message": "No data available"}

        # 按年内3日跟买成功率排序
        sorted_by_success_rate = data.sort_values(
            by="年内3日成功率", ascending=False
        ).head(10)

        # 按合计动用资金排序
        sorted_by_funds = data.sort_values(
            by="合计动用资金", ascending=False
        ).head(10)

        # 按年内上榜次数排序
        sorted_by_times = data.sort_values(
            by="年内上榜次数", ascending=False
        ).head(10)

        return {
            "success": True,
            "data": {
                "sorted_by_success_rate": sorted_by_success_rate.to_dict(orient="records"),
                "sorted_by_funds": sorted_by_funds.to_dict(orient="records"),
                "sorted_by_times": sorted_by_times.to_dict(orient="records"),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"stock_lh_yyb_most_sorted error: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def stock_lhb_ggtj_sina(symbol: str) -> Dict[str, Any]:
    """
    获取龙虎榜-个股上榜统计。

    参数：
        symbol (str): 时间范围，例如 "5" 表示最近 5 天。

    返回：
        dict: 包含成功状态和个股上榜统计数据。
    """
    import akshare as ak
    try:
        data = ak.stock_lhb_ggtj_sina(symbol=symbol)
        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_lhb_ggtj_sina error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_lhb_yytj_sina(symbol: str) -> Dict[str, Any]:
    """
    获取龙虎榜-营业上榜统计，并按上榜次数、累计购买额、累计卖出额分别排序后返回前10。

    参数：
        symbol (str): 时间范围，例如 "5" 表示最近 5 天，可选5、10、30、60。

    返回：
        dict: 包含成功状态和排序后的营业上榜统计数据。
    """
    import akshare as ak
    try:
        data = ak.stock_lhb_yytj_sina(symbol=symbol)
        if data.empty:
            return {"success": False, "message": "No data available"}

        # 按上榜次数排序
        sorted_by_times = data.sort_values(by="上榜次数", ascending=False).head(10)

        # 按累计购买额排序
        sorted_by_buy_amount = data.sort_values(by="累计买入额", ascending=False).head(10)

        # 按累计卖出额排序
        sorted_by_sell_amount = data.sort_values(by="累计卖出额", ascending=False).head(10)

        return {
            "success": True,
            "data": {
                "sorted_by_times": sorted_by_times.to_dict(orient="records"),
                "sorted_by_buy_amount": sorted_by_buy_amount.to_dict(orient="records"),
                "sorted_by_sell_amount": sorted_by_sell_amount.to_dict(orient="records"),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"stock_lhb_yytj_sina error: {e}")
        return {"success": False, "message": str(e)}



@mcp.tool()
def stock_lhb_jgmx_sina(date: str = None) -> Dict[str, Any]:
    """
    获取龙虎榜-机构席位成交明细，并可按指定日期过滤。

    参数：
        date (str): 可选，指定日期，格式为 "yyyy-mm-dd"。

    返回：
        dict: 包含成功状态和机构席位成交明细数据。
    """
    import akshare as ak
    try:
        data = ak.stock_lhb_jgmx_sina()
        if date:
            data["日期"] = data["日期"].astype(str)
            filtered_data = data[data["日期"] == date]
            if filtered_data.empty:
                return {"success": False, "message": f"No data available for date {date}"}
            data = filtered_data

        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_lhb_jgmx_sina error: {e}")
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    mcp.run()