"""
股票核心数据MCP服务器
提供基础的股票查询、实时价格、历史数据等功能
基于akshare但避免使用东财数据源
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import sys
import akshare as ak
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).resolve().parents[4]  # 从工具目录回到项目根目录
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

from mcp.server.fastmcp import FastMCP
from stock_cli.data.market_provider import MarketData
from stock_cli.data.stock_data import RealStockData

log_dir = project_root / "logs"
log_dir.mkdir(parents=True, exist_ok=True)

# 完全禁用MCP相关的控制台日志输出
for name in [
    "mcp",
    "mcp.server",
    "mcp.server.fastmcp",
    "mcp.server.lowlevel",
    "__main__",
]:
    logging.getLogger(name).setLevel(logging.CRITICAL)
    logging.getLogger(name).propagate = False
    logging.getLogger(name).handlers.clear()

from logging.handlers import RotatingFileHandler

def setup_logging(log_path: str, level=logging.CRITICAL, max_bytes=5*1024*1024, backup_count=5):
    handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger

logger = setup_logging("logs/mcp_stock_core.log")

# 创建MCP服务器
mcp = FastMCP("Stock Core Server")

# 初始化数据提供者
market_data = MarketData()
stock_data = RealStockData()


@mcp.tool()
def get_stock_realtime_price(symbol: str) -> Dict[str, Any]:
    """
    获取股票实时价格信息

    Args:
        symbol: 股票代码，如 "000001", "600519"

    Returns:
        包含股票实时价格信息的字典
    """
    try:
        logger.info(f"获取股票 {symbol} 实时价格")

        # 使用akshare获取实时价格（非东财接口）
        

        # 尝试获取个股实时行情
        df = ak.stock_zh_a_spot()

        # 查找指定股票
        stock_info = df[df["代码"] == symbol]

        if stock_info.empty:
            return {"success": False, "message": f"未找到股票 {symbol}", "data": None}

        row = stock_info.iloc[0]
        result = {
            "success": True,
            "symbol": symbol,
            "name": row["名称"],
            "current_price": float(row["最新价"]),
            "change_amount": float(row["涨跌额"]),
            "change_percent": float(row["涨跌幅"]),
            "volume": int(row["成交量"]) if row["成交量"] != "-" else 0,
            "turnover": float(row["成交额"]) if row["成交额"] != "-" else 0.0,
            "high": float(row["最高"]) if row["最高"] != "-" else 0.0,
            "low": float(row["最低"]) if row["最低"] != "-" else 0.0,
            "open": float(row["今开"]) if row["今开"] != "-" else 0.0,
            "pre_close": float(row["昨收"]) if row["昨收"] != "-" else 0.0,
            "timestamp": datetime.now().isoformat(),
        }

        return result

    except Exception as e:
        logger.error(f"获取股票价格失败: {str(e)}")
        return {
            "success": False,
            "message": f"获取股票价格失败: {str(e)}",
            "data": None,
        }


@mcp.tool()
def get_stock_history(
    symbol: str, period: str = "daily", days: int = 30
) -> Dict[str, Any]:
    """
    获取股票历史K线数据

    Args:
        symbol: 股票代码
        period: 周期，支持 "daily"(日线), "weekly"(周线), "monthly"(月线)
        days: 获取天数，默认30天

    Returns:
        包含历史K线数据的字典
    """
    try:
        logger.info(f"获取股票 {symbol} 历史数据，周期: {period}, 天数: {days}")


        # 计算开始日期
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

        # 使用腾讯数据源获取历史数据
        df = ak.stock_zh_a_hist_tx(
            symbol=symbol, start_date=start_date, end_date=end_date
        )

        if df.empty:
            return {
                "success": False,
                "message": f"未找到股票 {symbol} 的历史数据",
                "data": None,
            }

        # 转换数据格式
        history_data = []
        for _, row in df.iterrows():
            history_data.append(
                {
                    "date": row["日期"].strftime("%Y-%m-%d")
                    if hasattr(row["日期"], "strftime")
                    else str(row["日期"]),
                    "open": float(row["开盘"]),
                    "high": float(row["最高"]),
                    "low": float(row["最低"]),
                    "close": float(row["收盘"]),
                    "volume": int(row["成交量"]),
                }
            )

        # 按周期处理数据（如果需要）
        if period == "weekly":
            # 简单处理：每5个交易日取一个
            history_data = history_data[::5]
        elif period == "monthly":
            # 简单处理：每20个交易日取一个
            history_data = history_data[::20]

        return {
            "success": True,
            "symbol": symbol,
            "period": period,
            "data_points": len(history_data),
            "data": history_data[-days:],  # 确保不超过请求的天数
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取历史数据失败: {str(e)}")
        return {
            "success": False,
            "message": f"获取历史数据失败: {str(e)}",
            "data": None,
        }


@mcp.tool()
def mcp_stock_market_report():
    """
    获取A股实时行情，生成市场摘要报告（适合LLM输入）
    """
    # 获取实时行情
    df = ak.stock_zh_a_spot()
    # 涨幅榜
    top_gainers = df.sort_values("涨跌幅", ascending=False).head(5)
    # 跌幅榜
    top_losers = df.sort_values("涨跌幅", ascending=True).head(5)
    # 市场指数
    index_df = ak.stock_zh_index_spot()
    index_info = index_df[["指数名称", "最新价", "涨跌幅"]].head(3)

    # 组织报告文本
    report = []
    report.append(f"【A股市场实时简报】{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    report.append("主要指数：")
    for _, row in index_info.iterrows():
        report.append(f"- {row['指数名称']}: {row['最新价']}点，涨跌幅 {row['涨跌幅']}%")
    report.append("\n涨幅前五：")
    for _, row in top_gainers.iterrows():
        report.append(f"- {row['名称']}({row['代码']}): 涨幅 {row['涨跌幅']}%，成交额 {row['成交额']}万")
    report.append("\n跌幅前五：")
    for _, row in top_losers.iterrows():
        report.append(f"- {row['名称']}({row['代码']}): 跌幅 {row['涨跌幅']}%，成交额 {row['成交额']}万")
    report.append("\n市场简评：今日A股热点板块突出，涨跌分化明显。")

    return "\n".join(report)


@mcp.tool()
def search_stock_info(keyword: str) -> Dict[str, Any]:
    """
    根据关键词搜索股票信息

    Args:
        keyword: 搜索关键词（股票代码或名称）

    Returns:
        匹配的股票信息列表
    """
    try:
        logger.info(f"搜索股票: {keyword}")


        # 获取所有A股股票列表
        df = ak.stock_zh_a_spot()

        # 搜索匹配的股票
        keyword_upper = keyword.upper()
        matches = df[
            df["代码"].str.contains(keyword, na=False)
            | df["名称"].str.contains(keyword, na=False)
        ]

        if matches.empty:
            return {
                "success": False,
                "message": f"未找到关键词 '{keyword}' 相关的股票",
                "results": [],
            }

        # 转换结果
        # 转换为列表格式
        results = []
        for _, row in matches.iterrows():
            results.append(
                {
                    "name": row["名称"],
                    "code": row["代码"],
                    "current_price": float(row["最新价"])
                    if "最新价" in row and row["最新价"] != "-"
                    else 0.0,
                    "change_percent": float(row["涨跌幅"])
                    if "涨跌幅" in row and row["涨跌幅"] != "-"
                    else 0.0,
                }
            )

        return {
            "success": True,
            "keyword": keyword,
            "count": len(results),
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"搜索股票失败: {str(e)}")
        return {"success": False, "message": f"搜索股票失败: {str(e)}", "results": []}


@mcp.tool()
def get_company_profile(symbol: str) -> Dict[str, Any]:
    """
    获取公司基本信息

    Args:
        symbol: 股票代码

    Returns:
        公司基本信息字典
    """
    try:
        logger.info(f"获取公司 {symbol} 基本信息")


        # 使用雪球数据获取公司基本信息
        df = ak.stock_individual_basic_info_xq(
            symbol=f"SH{symbol}" if symbol.startswith("6") else f"SZ{symbol}"
        )

        if df.empty:
            return {
                "success": False,
                "message": f"未找到股票 {symbol} 的公司信息",
                "data": None,
            }

        # 转换为字典格式
        info_dict = {}
        for _, row in df.iterrows():
            info_dict[row["item"]] = row["value"]

        # 提取关键信息
        profile = {
            "success": True,
            "symbol": symbol,
            "company_name": info_dict.get("名称", ""),
            "industry": info_dict.get("所属行业", ""),
            "listing_date": info_dict.get("上市时间", ""),
            "total_shares": info_dict.get("总股本", ""),
            "circulating_shares": info_dict.get("流通股", ""),
            "market_cap": info_dict.get("总市值", ""),
            "pe_ratio": info_dict.get("市盈率(动)", ""),
            "pb_ratio": info_dict.get("市净率", ""),
            "business_scope": info_dict.get("主营业务", ""),
            "timestamp": datetime.now().isoformat(),
        }

        return profile

    except Exception as e:
        logger.error(f"获取公司信息失败: {str(e)}")
        return {
            "success": False,
            "message": f"获取公司信息失败: {str(e)}",
            "data": None,
        }


if __name__ == "__main__":
    # 日志信息已移至main.py中统一处理
    mcp.run()
