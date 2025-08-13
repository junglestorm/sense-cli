"""
盘口异动工具模块：提供获取东方财富盘口异动数据的功能。
"""

import logging
from datetime import datetime
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("Stock Changes Tools Server")

@mcp.tool()
def stock_changes_em(symbol: str) -> Dict[str, Any]:
    """
    获取指定 symbol 的最近交易日盘口异动数据。

    参数：
        symbol (str): 指定的盘口异动类型，例如以下选项之一：
            '火箭发射', '快速反弹', '大笔买入', '封涨停板', '打开跌停板', 
            '有大买盘', '竞价上涨', '高开5日线', '向上缺口', '60日新高', 
            '60日大幅上涨', '加速下跌', '高台跳水', '大笔卖出', '封跌停板', 
            '打开涨停板', '有大卖盘', '竞价下跌', '低开5日线', '向下缺口', 
            '60日新低', '60日大幅下跌'

    返回：
        dict: 包含成功状态和盘口异动数据。
    """
    import akshare as ak
    try:
        data = ak.stock_changes_em(symbol=symbol)
        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_changes_em error: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def stock_board_change_em(board_name: str = None, min_change: float = None) -> Dict[str, Any]:
    """
    获取当日板块异动详情数据。

    参数：
        board_name (str, 可选): 筛选特定板块名称。
        min_change (float, 可选): 筛选涨跌幅大于等于指定值的板块。

    返回：
        dict: 包含成功状态和板块异动详情数据。
    """
    import akshare as ak
    try:
        data = ak.stock_board_change_em()
        if board_name is not None:
            data = data[data['板块名称'] == board_name]
        if min_change is not None:
            data = data[data['涨跌幅'] >= min_change]
        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_board_change_em error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_zt_pool_em(
    date: str,
    min_turnover: float = None,
    min_limit_count: int = None,
    min_price: float = None,
    max_price: float = None,
    min_market_cap: float = None,
    max_market_cap: float = None,
    min_total_market_cap: float = None,
    max_total_market_cap: float = None,
    min_zb_count: int = None,
    max_zb_count: int = None
) -> Dict[str, Any]:
    """
    获取指定日期的涨停股池数据，并支持多种筛选条件。

    参数：
        date (str): 指定的日期，格式为 'YYYYMMDD'。
        min_turnover (float, 可选): 筛选换手率大于等于指定值的股票。
        min_limit_count (int, 可选): 筛选连板数大于等于指定值的股票。
        min_price (float, 可选): 筛选最新价大于等于指定值的股票。
        max_price (float, 可选): 筛选最新价小于等于指定值的股票。
        min_market_cap (float, 可选): 筛选流通市值大于等于指定值的股票。
        max_market_cap (float, 可选): 筛选流通市值小于等于指定值的股票。
        min_total_market_cap (float, 可选): 筛选总市值大于等于指定值的股票。
        max_total_market_cap (float, 可选): 筛选总市值小于等于指定值的股票。
        min_zb_count (int, 可选): 筛选炸板次数大于等于指定值的股票。
        max_zb_count (int, 可选): 筛选炸板次数小于等于指定值的股票。

    返回：
        dict: 包含成功状态和涨停股池数据。
    """
    import akshare as ak
    try:
        data = ak.stock_zt_pool_em(date=date)
        if min_turnover is not None:
            data = data[data['换手率'] >= min_turnover]
        if min_limit_count is not None:
            data = data[data['连板数'] >= min_limit_count]
        if min_price is not None:
            data = data[data['最新价'] >= min_price]
        if max_price is not None:
            data = data[data['最新价'] <= max_price]
        if min_market_cap is not None:
            data = data[data['流通市值'] >= min_market_cap]
        if max_market_cap is not None:
            data = data[data['流通市值'] <= max_market_cap]
        if min_total_market_cap is not None:
            data = data[data['总市值'] >= min_total_market_cap]
        if max_total_market_cap is not None:
            data = data[data['总市值'] <= max_total_market_cap]
        if min_zb_count is not None:
            data = data[data['炸板次数'] >= min_zb_count]
        if max_zb_count is not None:
            data = data[data['炸板次数'] <= max_zb_count]
        return {
            "success": True,
            "data": data.to_dict(orient="records"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"stock_zt_pool_em error: {e}")
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    mcp.run()