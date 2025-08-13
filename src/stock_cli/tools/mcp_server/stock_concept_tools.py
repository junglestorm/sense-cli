"""
概念板块相关工具模块：包含与概念板块信息、指数等相关的功能工具。
"""

import logging
from datetime import datetime
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("A股个股概念板块工具")

@mcp.tool()
def stock_board_concept_index_ths(symbol: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    同花顺-板块-概念板块-指数日频率数据查询工具。

    默认时间范围为最近一年，支持计算月线、周线，并返回：
    - 最近 15 天的日线数据列表
    - 周线数据列表
    - 月线数据列表

    参数：
        symbol (str): 概念板块名称，例如 "阿里巴巴概念"。
        start_date (str): 开始时间，格式 "YYYYMMDD"，默认最近一年。
        end_date (str): 结束时间，格式 "YYYYMMDD"，默认今天。

    返回：
        dict: {
            success: bool,
            data: {
                "daily": 最近 15 天的日线数据,
                "weekly": 周线数据,
                "monthly": 月线数据
            },
            meta: { symbol, start_date, end_date },
            timestamp: ISO 时间
        }
    """
    import akshare as ak
    import pandas as pd
    from datetime import datetime, timedelta

    today = datetime.now()
    if not end_date:
        end_date = today.strftime("%Y%m%d")
    if not start_date:
        start_date = (today - timedelta(days=365)).strftime("%Y%m%d")

    try:
        df = ak.stock_board_concept_index_ths(symbol=symbol, start_date=start_date, end_date=end_date)
    except Exception as e:
        logger.error(f"stock_board_concept_index_ths fetch error: {e}")
        return {"success": False, "message": str(e)}

    if df is None or df.empty:
        return {"success": False, "message": "No data returned"}

    try:
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期")

        # 最近 15 天的日线数据
        daily_data = df.tail(15).to_dict(orient="records")

        # 计算周线数据
        df["周"] = df["日期"].dt.to_period("W").apply(lambda r: r.start_time)
        weekly_data = df.groupby("周").agg({
            "开盘价": "first",
            "最高价": "max",
            "最低价": "min",
            "收盘价": "last",
            "成交量": "sum",
            "成交额": "sum"
        }).reset_index().rename(columns={"周": "日期"}).to_dict(orient="records")

        # 计算月线数据
        df["月"] = df["日期"].dt.to_period("M").apply(lambda r: r.start_time)
        monthly_data = df.groupby("月").agg({
            "开盘价": "first",
            "最高价": "max",
            "最低价": "min",
            "收盘价": "last",
            "成交量": "sum",
            "成交额": "sum"
        }).reset_index().rename(columns={"月": "日期"}).to_dict(orient="records")

        return {
            "success": True,
            "data": {
                "daily": daily_data,
                "weekly": weekly_data,
                "monthly": monthly_data
            },
            "meta": {
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_board_concept_index_ths processing error: {e}")
        return {"success": False, "message": f"processing error: {e}"}


@mcp.tool()
def stock_board_concept_info_ths(symbol: str) -> Dict[str, Any]:
    """
    同花顺-板块-概念板块-板块简介查询工具。

    参数：
        symbol (str): 概念板块名称，例如 "阿里巴巴概念"。

    返回：
        dict: {
            success: bool,
            data: 概念板块简介数据列表,
            meta: { symbol },
            timestamp: ISO 时间
        }
    """
    import akshare as ak

    try:
        df = ak.stock_board_concept_info_ths(symbol=symbol)
    except Exception as e:
        logger.error(f"stock_board_concept_info_ths fetch error: {e}")
        return {"success": False, "message": str(e)}

    if df is None or df.empty:
        return {"success": False, "message": "No data returned"}

    try:
        data = df.to_dict(orient="records")
        return {
            "success": True,
            "data": data,
            "meta": {
                "symbol": symbol
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_board_concept_info_ths processing error: {e}")
        return {"success": False, "message": f"processing error: {e}"}
@mcp.tool()
def stock_board_concept_info(symbols: list) -> Dict[str, Any]:
    """
    获取同花顺指定概念板块列表的简介数据。

    参数：
        symbols (list): 概念名称列表，例如["阿里巴巴概念", "新能源概念"]。

    返回：
        dict: 包含成功状态和每个概念板块的简介数据。
    """
    import akshare as ak
    results = []
    try:
        for symbol in symbols:
            data = ak.stock_board_concept_info_ths(symbol=symbol)
            results.append({
                "symbol": symbol,
                "data": data.to_dict(orient="records")
            })
        return {
            "success": True,
            "data": results,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_board_concept_info error: {e}")
        return {"success": False, "message": str(e)}
    

if __name__ == "__main__":
    mcp.run()
