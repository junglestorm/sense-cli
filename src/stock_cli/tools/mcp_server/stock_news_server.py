"""
股票新闻和分析MCP服务器
提供股票新闻、资金流向、技术分析等功能
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

from mcp.server.fastmcp import FastMCP

log_dir = Path(__file__).resolve().parents[3] / "logs"
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

logger = setup_logging("logs/mcp_stock_news.log")

# 创建MCP服务器
mcp = FastMCP("Stock News Analysis Server")


@mcp.tool()
def get_stock_news(symbol: str, limit: int = 10) -> Dict[str, Any]:
    """
    获取个股相关新闻

    Args:
        symbol: 股票代码
        limit: 新闻数量限制，默认10条

    Returns:
        包含新闻列表的字典
    """
    try:
        logger.info(f"获取股票 {symbol} 相关新闻")

        import akshare as ak

        # 先获取股票名称
        stock_info_df = ak.stock_zh_a_spot()
        stock_info = stock_info_df[stock_info_df["代码"] == symbol]

        if stock_info.empty:
            return {"success": False, "message": f"未找到股票 {symbol}", "news": []}

        stock_name = stock_info.iloc[0]["名称"]

        # 使用股票名称搜索新闻
        news_df = ak.stock_news_em(symbol=stock_name)

        if news_df.empty:
            return {
                "success": True,
                "symbol": symbol,
                "stock_name": stock_name,
                "count": 0,
                "news": [],
                "message": "暂无相关新闻",
            }

        # 转换新闻数据
        news_list = []
        for _, row in news_df.head(limit).iterrows():
            news_list.append(
                {
                    "title": row["新闻标题"],
                    "content": row["新闻内容"][:200] + "..."
                    if len(row["新闻内容"]) > 200
                    else row["新闻内容"],
                    "publish_time": row["发布时间"],
                    "source": row["文章来源"],
                    "link": row.get("新闻链接", ""),
                }
            )

        return {
            "success": True,
            "symbol": symbol,
            "stock_name": stock_name,
            "count": len(news_list),
            "news": news_list,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取股票新闻失败: {str(e)}")
        return {"success": False, "message": f"获取股票新闻失败: {str(e)}", "news": []}


@mcp.tool()
def get_market_sentiment() -> Dict[str, Any]:
    """
    获取市场情绪指标

    Returns:
        市场情绪相关数据
    """
    try:
        logger.info("获取市场情绪指标")

        import akshare as ak

        # 获取涨跌停数据作为情绪指标
        try:
            # 获取A股实时数据
            df = ak.stock_zh_a_spot()

            # 计算涨跌情况
            rising_count = len(df[df["涨跌幅"] > 0])
            falling_count = len(df[df["涨跌幅"] < 0])
            unchanged_count = len(df[df["涨跌幅"] == 0])
            total_count = len(df)

            # 计算涨停跌停
            limit_up = len(df[df["涨跌幅"] >= 9.8])  # 近似涨停
            limit_down = len(df[df["涨跌幅"] <= -9.8])  # 近似跌停

            sentiment_data = {
                "success": True,
                "total_stocks": total_count,
                "rising_stocks": rising_count,
                "falling_stocks": falling_count,
                "unchanged_stocks": unchanged_count,
                "limit_up_stocks": limit_up,
                "limit_down_stocks": limit_down,
                "rising_ratio": round(rising_count / total_count * 100, 2)
                if total_count > 0
                else 0,
                "falling_ratio": round(falling_count / total_count * 100, 2)
                if total_count > 0
                else 0,
                "market_sentiment": "积极"
                if rising_count > falling_count
                else "谨慎"
                if rising_count < falling_count
                else "平衡",
                "timestamp": datetime.now().isoformat(),
            }

            return sentiment_data

        except Exception as e:
            logger.error(f"获取实时数据失败: {str(e)}")
            # 返回错误信息，不使用模拟数据
            return {
                "success": False,
                "message": f"获取市场情绪数据失败: {str(e)}",
                "market_sentiment": "数据获取失败",
                "timestamp": datetime.now().isoformat(),
            }

    except Exception as e:
        logger.error(f"获取市场情绪失败: {str(e)}")
        return {"success": False, "message": f"获取市场情绪失败: {str(e)}"}


@mcp.tool()
def calculate_technical_indicators(
    symbol: str, indicator: str = "ma"
) -> Dict[str, Any]:
    """
    计算技术指标

    Args:
        symbol: 股票代码
        indicator: 技术指标类型，支持 "ma"(移动平均), "rsi"(相对强弱指数)

    Returns:
        技术指标计算结果
    """
    try:
        logger.info(f"计算股票 {symbol} 的技术指标: {indicator}")

        import akshare as ak

        # 获取历史数据
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")

        df = ak.stock_zh_a_hist_tx(
            symbol=symbol, start_date=start_date, end_date=end_date
        )

        if df.empty:
            return {
                "success": False,
                "message": f"未找到股票 {symbol} 的历史数据",
                "data": None,
            }

        result = {
            "success": True,
            "symbol": symbol,
            "indicator": indicator,
            "timestamp": datetime.now().isoformat(),
        }

        if indicator == "ma":
            # 计算移动平均线
            df["MA5"] = df["收盘"].rolling(window=5).mean()
            df["MA10"] = df["收盘"].rolling(window=10).mean()
            df["MA20"] = df["收盘"].rolling(window=20).mean()

            latest = df.iloc[-1]
            result.update(
                {
                    "current_price": float(latest["收盘"]),
                    "ma5": round(float(latest["MA5"]), 2),
                    "ma10": round(float(latest["MA10"]), 2),
                    "ma20": round(float(latest["MA20"]), 2),
                    "trend_analysis": {
                        "short_trend": "上升"
                        if latest["收盘"] > latest["MA5"]
                        else "下降",
                        "medium_trend": "上升"
                        if latest["MA5"] > latest["MA10"]
                        else "下降",
                        "long_trend": "上升"
                        if latest["MA10"] > latest["MA20"]
                        else "下降",
                    },
                }
            )

        elif indicator == "rsi":
            # 计算RSI
            delta = df["收盘"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            latest_rsi = rsi.iloc[-1]
            result.update(
                {
                    "current_price": float(df.iloc[-1]["收盘"]),
                    "rsi": round(float(latest_rsi), 2),
                    "rsi_signal": "超买"
                    if latest_rsi > 70
                    else "超卖"
                    if latest_rsi < 30
                    else "正常",
                }
            )

        return result

    except Exception as e:
        logger.error(f"计算技术指标失败: {str(e)}")
        return {
            "success": False,
            "message": f"计算技术指标失败: {str(e)}",
            "data": None,
        }


@mcp.tool()
def get_hot_stocks_analysis(limit: int = 20) -> Dict[str, Any]:
    """
    获取热门股票分析

    Args:
        limit: 返回股票数量

    Returns:
        热门股票分析数据
    """
    try:
        logger.info(f"获取热门股票分析，数量: {limit}")

        import akshare as ak

        # 获取实时行情数据
        df = ak.stock_zh_a_spot()

        if df.empty:
            return {"success": False, "message": "无法获取股票数据", "data": []}

        # 按成交额排序找出热门股票
        df_sorted = df.nlargest(limit, "成交额")

        hot_stocks = []
        for _, row in df_sorted.iterrows():
            hot_stocks.append(
                {
                    "symbol": row["代码"],
                    "name": row["名称"],
                    "current_price": float(row["最新价"])
                    if row["最新价"] != "-"
                    else 0.0,
                    "change_percent": float(row["涨跌幅"])
                    if row["涨跌幅"] != "-"
                    else 0.0,
                    "change_amount": float(row["涨跌额"])
                    if row["涨跌额"] != "-"
                    else 0.0,
                    "turnover": float(row["成交额"]) if row["成交额"] != "-" else 0.0,
                    "volume": int(row["成交量"]) if row["成交量"] != "-" else 0,
                    "turnover_rate": float(row["换手率"])
                    if "换手率" in row and row["换手率"] != "-"
                    else 0.0,
                }
            )

        # 简单的热度分析
        analysis = {
            "total_analyzed": len(hot_stocks),
            "rising_count": len([s for s in hot_stocks if s["change_percent"] > 0]),
            "falling_count": len([s for s in hot_stocks if s["change_percent"] < 0]),
            "avg_change_percent": round(
                sum([s["change_percent"] for s in hot_stocks]) / len(hot_stocks), 2
            ),
            "most_active": hot_stocks[0] if hot_stocks else None,
        }

        return {
            "success": True,
            "analysis": analysis,
            "hot_stocks": hot_stocks,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"获取热门股票分析失败: {str(e)}")
        return {
            "success": False,
            "message": f"获取热门股票分析失败: {str(e)}",
            "data": [],
        }


if __name__ == "__main__":
    # 日志信息已移至main.py中统一处理
    mcp.run()
