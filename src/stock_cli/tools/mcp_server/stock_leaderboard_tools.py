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

@mcp.tool()
def stock_zt_pool_previous_em(date: str) -> Dict[str, Any]:
    """
    昨日涨停股池查询。
    限制: 单次返回指定 date 的昨日涨停股池数据; 该接口只能获取近期的数据。

    参数:
        date (str): 交易日期, 格式如 '20240415'。

    返回:
        dict: { success: bool, data: List[Dict], timestamp: str }。
              data 字段包含列: 序号, 代码, 名称, 涨跌幅(%), 最新价, 涨停价, 成交额, 流通市值, 总市值,
              换手率(%), 涨速(%), 振幅(%), 昨日封板时间(HHMMSS), 昨日连板数, 涨停统计, 所属行业。
    """
    import akshare as ak
    try:
        df = ak.stock_zt_pool_previous_em(date=date)
        # 统一列名处理（若列存在则保持原样，不做重命名，以免 akshare 更新导致错误）
        records = df.to_dict(orient="records")
        return {
            "success": True,
            "data": records,
            "timestamp": datetime.now().isoformat(),
            "meta": {
                "source": "EastMoney",
                "date": date,
                "count": len(records)
            }
        }
    except Exception as e:
        logger.error(f"stock_zt_pool_previous_em error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_zt_pool_strong_em(date: str) -> Dict[str, Any]:
    """
    强势股池查询。

    东方财富网-行情中心-涨停板行情-强势股池。
    接口: stock_zt_pool_strong_em
    目标地址: https://quote.eastmoney.com/ztb/detail#type=qsgc
    限制: 单次返回指定 date 的强势股池数据；该接口只能获取近期的数据。

    参数:
        date (str): 交易日期, 格式如 '20241009'。

    返回:
        dict: { success: bool, data: List[Dict], timestamp: str }。
              data 列示例: 序号, 代码, 名称, 涨跌幅(%), 最新价, 涨停价, 成交额, 流通市值, 总市值,
              换手率(%), 涨速(%), 是否新高, 量比, 涨停统计, 入选理由, 所属行业。
    """
    import akshare as ak
    try:
        df = ak.stock_zt_pool_strong_em(date=date)
        records = df.to_dict(orient="records")
        return {
            "success": True,
            "data": records,
            "timestamp": datetime.now().isoformat(),
            "meta": {
                "source": "EastMoney",
                "date": date,
                "count": len(records)
            }
        }
    except Exception as e:
        logger.error(f"stock_zt_pool_strong_em error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_zt_pool_zbgc_em(date: str) -> Dict[str, Any]:
    """
    炸板股池查询。

    东方财富网-行情中心-涨停板行情-炸板股池。
    接口: stock_zt_pool_zbgc_em
    目标地址: https://quote.eastmoney.com/ztb/detail#type=zbgc
    限制: 单次返回指定 date 的炸板股池数据；该接口只能获取近期的数据。

    参数:
        date (str): 交易日期, 格式如 '20241011'。

    返回:
        dict: { success: bool, data: List[Dict], timestamp: str }。
              data 列示例: 序号, 代码, 名称, 涨跌幅(%), 最新价, 涨停价, 成交额, 流通市值, 总市值,
              换手率(%), 涨速, 首次封板时间(HHMMSS), 炸板次数, 涨停统计, 振幅, 所属行业。
    """
    import akshare as ak
    try:
        df = ak.stock_zt_pool_zbgc_em(date=date)
        records = df.to_dict(orient="records")
        return {
            "success": True,
            "data": records,
            "timestamp": datetime.now().isoformat(),
            "meta": {"source": "EastMoney", "date": date, "count": len(records)}
        }
    except Exception as e:
        logger.error(f"stock_zt_pool_zbgc_em error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def stock_zt_pool_dtgc_em(date: str) -> Dict[str, Any]:
    """
    跌停股池查询。

    东方财富网-行情中心-涨停板行情-跌停股池。
    接口: stock_zt_pool_dtgc_em
    目标地址: https://quote.eastmoney.com/ztb/detail#type=dtgc
    限制: 单次返回指定 date 的跌停股池数据；该接口只能获取近期的数据。

    参数:
        date (str): 交易日期, 格式如 '20241011'。

    返回:
        dict: { success: bool, data: List[Dict], timestamp: str }。
              data 列示例: 序号, 代码, 名称, 涨跌幅(%), 最新价, 成交额, 流通市值, 总市值, 动态市盈率,
              换手率(%), 封单资金, 最后封板时间(HHMMSS), 板上成交额, 连续跌停, 开板次数, 所属行业。
    """
    import akshare as ak
    try:
        df = ak.stock_zt_pool_dtgc_em(date=date)
        records = df.to_dict(orient="records")
        return {
            "success": True,
            "data": records,
            "timestamp": datetime.now().isoformat(),
            "meta": {"source": "EastMoney", "date": date, "count": len(records)}
        }
    except Exception as e:
        logger.error(f"stock_zt_pool_dtgc_em error: {e}")
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    mcp.run()