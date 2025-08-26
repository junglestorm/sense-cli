"""
股票基本面的基本数据工具：提供主营构成、财务指标、估值等核心数据。
"""

import logging
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("Fundamental Data Tools")


@mcp.tool()
def get_stock_main_business(symbol: str) -> Dict[str, Any]:
    """
    获取单只股票的主营业务构成数据。

    参数：
        symbol (str): 股票代码，例如 "600519"

    返回：
        dict: 主营构成（业务名称、收入、占比）
    """
    import akshare as ak
    from datetime import datetime
    try:
        # 获取主营构成，使用修正后的接口名
        df = ak.stock_zygc_ym(symbol=symbol)
        if df.empty:
            return {"success": False, "message": "No main business data"}

        # 返回所有记录
        records = df.to_dict('records')
        return {
            "success": True,
            "data": records,
            "count": len(records),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@mcp.tool()
def get_stock_financial_metrics(symbol: str, report_type: str = "资产负债表") -> Dict[str, Any]:
    """
    获取股票的财务指标数据。

    参数：
        symbol (str): 股票代码
        report_type (str): 报告类型，可选："资产负债表", "利润表", "现金流量表"

    返回：
        dict: 财务数据表格
    """
    import akshare as ak
    from datetime import datetime
    try:
        # 使用新浪财经的财务报告接口
        # 注意：该接口可能需要处理报告类型映射
        df = ak.stock_financial_report_sina(symbol=symbol, report_type=report_type)
        if df.empty:
            return {"success": False, "message": "No financial data"}

        return {
            "success": True,
            "data": df.to_dict('records'),
            "report_type": report_type,
            "count": len(df),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@mcp.tool()
def get_stock_valuation(symbol: str) -> Dict[str, Any]:
    """
    获取股票的估值指标（PE, PB, PS, ROE等）。

    参数：
        symbol (str): 股票代码

    返回：
        dict: 估值指标
    """
    import akshare as ak
    from datetime import datetime
    try:
        # 创建一个字典来存储最终的估值数据
        valuation_data = {"symbol": symbol}
        
        # 定义要获取的指标列表
        indicators = ["市盈率(TTM)", "市净率", "市销率(TTM)", "净资产收益率(ROE)"]
        
        for indicator in indicators:
            # 使用百度股市通接口获取单个指标的数据
            df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator=indicator)
            if not df.empty:
                # 取最新的数据
                latest_value = df['value'].iloc[-1]
                # 将指标值存入字典，键名进行简化
                if indicator == "市盈率(TTM)":
                    valuation_data["pe_ttm"] = latest_value
                elif indicator == "市净率":
                    valuation_data["pb"] = latest_value
                elif indicator == "市销率(TTM)":
                    valuation_data["ps_ttm"] = latest_value
                elif indicator == "净资产收益率(ROE)":
                    valuation_data["roe"] = latest_value
            else:
                # 如果某个指标获取失败，设为None
                key_mapping = {
                    "市盈率(TTM)": "pe_ttm",
                    "市净率": "pb", 
                    "市销率(TTM)": "ps_ttm",
                    "净资产收益率(ROE)": "roe"
                }
                valuation_data[key_mapping.get(indicator)] = None

        return {
            "success": True,
            "data": valuation_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@mcp.tool()
def get_stock_summary(symbol: str) -> Dict[str, Any]:
    """
    获取股票的综合概要信息（名称、行业、市值、价格等）。

    参数：
        symbol (str): 股票代码

    返回：
        dict: 股票概要
    """
    import akshare as ak
    from datetime import datetime
    try:
        # 获取实时行情
        df = ak.stock_zh_a_spot_em()
        stock_info = df[df['代码'] == symbol]
        if stock_info.empty:
            return {"success": False, "message": "Stock not found"}

        info = stock_info.iloc[0]
        return {
            "success": True,
            "data": {
                "symbol": symbol,
                "name": info['名称'],
                "current_price": info['最新价'],
                "change_percent": info['涨跌幅'],
                "volume": info['成交量'],
                "market_cap": info['总市值'],
                "circulating_cap": info['流通市值'],
                "industry": info['所属行业']
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    mcp.run()