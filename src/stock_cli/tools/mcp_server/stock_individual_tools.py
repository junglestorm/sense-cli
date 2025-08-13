"""
个股相关工具模块：包含与个股信息、资金流等相关的功能工具。
"""

import logging
from datetime import datetime
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("A股个股相关工具")

@mcp.tool()
def stock_main_business(symbols: list) -> Dict[str, Any]:
    """
    获取股票列表的主营介绍数据。

    参数：
        symbols (list): 股票代码列表，例如["000066", "000001"]。

    返回：
        dict: 包含成功状态和每只股票的主营介绍数据。
    """
    import akshare as ak
    results = []
    try:
        for symbol in symbols:
            data = ak.stock_zyjs_ths(symbol=symbol)
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
        logger.error(f"stock_main_business error: {e}")
        return {"success": False, "message": str(e)}



@mcp.tool()
def stock_bid_ask(symbols: list) -> Dict[str, Any]:
    """
    获取指定股票列表的行情报价数据。

    参数：
        symbols (list): 股票代码列表，例如["000001", "000002"]。

    返回：
        dict: 包含成功状态和每只股票的行情报价数据。
    """
    import akshare as ak
    results = []
    try:
        for symbol in symbols:
            data = ak.stock_bid_ask_em(symbol=symbol)
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
        logger.error(f"stock_bid_ask error: {e}")
        return {"success": False, "message": str(e)}




@mcp.tool()
def stock_fund_flow_individual(symbol: str) -> Dict[str, Any]:
    """
    同花顺-数据中心-资金流向-个股资金流查询工具。

    根据 symbol 不同类型(“即时”, “3日排行”, “5日排行”, “10日排行”, “20日排行”)，调用
    akshare 接口 stock_fund_flow_individual(symbol=...) 获取数据，并执行如下排序逻辑：

    1. 当 symbol == "即时" 时：
       - 按 "换手率" 由高到低排序取前 30 条，字段值可能为形如 "5.23%" 的字符串，需要转成浮点数。
       - 按 "成交额" 由高到低排序取前 30 条，字段值可能带有“万/亿”单位（例如 "11.50亿"），需换算为数值(元)。
       - 返回结构包含 keys: {"top_by_turnover_rate", "top_by_amount"}。

    2. 当 symbol 为 "3日排行"、"5日排行"、"10日排行" 或 "20日排行" 时：
       - 按 "阶段涨跌幅"（如 "72.85%"）由高到低排序取前 30 条。
       - 按 "连续换手率"（如 "103.83%"）由高到低排序取前 30 条。
       - 返回结构包含 keys: {"top_by_stage_change", "top_by_cont_turnover"}。

    3. 数值解析规则：
       - 百分比: 去掉末尾 % 后转 float，例如 "72.85%" -> 72.85。
       - 金额: 支持 “亿” (×1e8), “万” (×1e4); 纯数字或带小数点直接转; 其它无法解析的置为 0。
       - 去除可能的逗号分隔符。

    返回：
        dict: {
          success: bool,
          data: { 分排序结果列表 },
          meta: { symbol, counts },
          timestamp: ISO 时间
        }
    """
    import akshare as ak
    import re
    import math
    VALID_SYMBOLS = ["即时", "3日排行", "5日排行", "10日排行", "20日排行"]
    if symbol not in VALID_SYMBOLS:
        return {"success": False, "message": f"symbol 必须为 {VALID_SYMBOLS}"}

    def parse_percent(val):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return 0.0
        s = str(val).strip()
        if not s:
            return 0.0
        if s.endswith('%'):
            s = s[:-1]
        s = s.replace(',', '')
        try:
            return float(s)
        except Exception:
            return 0.0

    def parse_amount(val):
        if val is None:
            return 0.0
        s = str(val).strip()
        if not s:
            return 0.0
        s = s.replace(',', '')
        mult = 1.0
        if s.endswith('亿'):
            mult = 1e8
            s = s[:-1]
        elif s.endswith('万'):
            mult = 1e4
            s = s[:-1]
        # 处理类似 "-1.30亿" 在前面先截取单位后的符号残留
        s = s.strip()
        # 若存在其它非数字/小数/负号字符，尝试用正则提取
        match = re.search(r'-?\d+(?:\.\d+)?', s)
        if match:
            try:
                return float(match.group()) * mult
            except Exception:
                return 0.0
        try:
            return float(s) * mult
        except Exception:
            return 0.0

    try:
        df = ak.stock_fund_flow_individual(symbol=symbol)
    except Exception as e:
        logger.error(f"stock_fund_flow_individual fetch error: {e}")
        return {"success": False, "message": str(e)}

    if df is None or df.empty:
        return {"success": False, "message": "No data returned"}

    result_data = {}

    try:
        if symbol == "即时":
            # 字段名称预期: 换手率, 成交额
            df_copy = df.copy()
            if "换手率" in df_copy.columns:
                df_copy["_换手率数值"] = df_copy["换手率"].apply(parse_percent)
                top_turnover = df_copy.sort_values("_换手率数值", ascending=False).head(30)
                result_data["top_by_turnover_rate"] = top_turnover.drop(columns=[c for c in ["_换手率数值"] if c in top_turnover.columns]).to_dict(orient="records")
            else:
                result_data["top_by_turnover_rate"] = []

            if "成交额" in df_copy.columns:
                df_copy["_成交额数值"] = df_copy["成交额"].apply(parse_amount)
                top_amount = df_copy.sort_values("_成交额数值", ascending=False).head(30)
                result_data["top_by_amount"] = top_amount.drop(columns=[c for c in ["_成交额数值"] if c in top_amount.columns]).to_dict(orient="records")
            else:
                result_data["top_by_amount"] = []
        else:
            # 阶段排行: 字段 阶段涨跌幅, 连续换手率
            df_copy = df.copy()
            if "阶段涨跌幅" in df_copy.columns:
                df_copy["_阶段涨跌幅数值"] = df_copy["阶段涨跌幅"].apply(parse_percent)
                top_stage = df_copy.sort_values("_阶段涨跌幅数值", ascending=False).head(30)
                result_data["top_by_stage_change"] = top_stage.drop(columns=[c for c in ["_阶段涨跌幅数值"] if c in top_stage.columns]).to_dict(orient="records")
            else:
                result_data["top_by_stage_change"] = []

            if "连续换手率" in df_copy.columns:
                df_copy["_连续换手率数值"] = df_copy["连续换手率"].apply(parse_percent)
                top_cont_turnover = df_copy.sort_values("_连续换手率数值", ascending=False).head(30)
                result_data["top_by_cont_turnover"] = top_cont_turnover.drop(columns=[c for c in ["_连续换手率数值"] if c in top_cont_turnover.columns]).to_dict(orient="records")
            else:
                result_data["top_by_cont_turnover"] = []
    except Exception as e:
        logger.error(f"stock_fund_flow_individual processing error: {e}")
        return {"success": False, "message": f"processing error: {e}"}

    return {
        "success": True,
        "data": result_data,
        "meta": {
            "symbol": symbol,
            "source": "ths",
            "raw_count": len(df),
            "generated_keys": list(result_data.keys())
        },
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    mcp.run()
