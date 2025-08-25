"""
个股深度洞察工具：提供技术、资金、龙虎榜、营业部等深度分析。
"""

import logging
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("Stock Insight Tools")


@mcp.tool()
def get_stock_metrics(stock_codes: list) -> Dict[str, Any]:
    """
    获取多个个股的日线、周线、月线技术指标，包括高低值及支撑阻力。

    参数：
        stock_codes (list): 股票代码列表，例如 ["600519", "000001"]

    返回：
        dict: 包含所有请求股票多周期技术指标和支撑阻力位的原始数据。
    """
    import akshare as ak
    import pandas as pd
    import talib
    import datetime

    try:
        all_metrics = {}

        for code in stock_codes:
            stock_data = {}

            # 获取日线数据
            for freq in ['daily', 'weekly', 'monthly']: # 使用AKShare的period参数 [[32]]
                df = ak.stock_zh_a_hist(symbol=code, period=freq, adjust="qfq")
                if df.empty or len(df) < 60:
                    stock_data[freq] = {"error": "Not enough data"}
                    continue

                # 计算常用指标
                close = df['收盘'].values
                high = df['最高'].values
                low = df['最低'].values

                df['MA5'] = talib.SMA(close, timeperiod=5)
                df['MA20'] = talib.SMA(close, timeperiod=20)
                df['MA60'] = talib.SMA(close, timeperiod=60)
                df['MACD'], df['MACD_Signal'], df['MACD_Hist'] = talib.MACD(close)
                df['RSI'] = talib.RSI(close)
                df['K'], df['D'] = talib.STOCH(high, low, close)
                df['J'] = 3 * df['K'] - 2 * df['D']
                df['BOLL_UPPER'], df['BOLL_MIDDLE'], df['BOLL_LOWER'] = talib.BBANDS(close)

                # 计算周期内最高值和最低值
                recent_high = df['最高'].tail(20).max() # 近20期高点
                recent_low = df['最低'].tail(20).min()  # 近20期低点

                # 计算简单支撑位和阻力位 (使用枢轴点方法) [[12]]
                last_row = df.iloc[-1]
                pivot = (last_row['最高'] + last_row['最低'] + last_row['收盘']) / 3
                resistance = 2 * pivot - last_row['最低'] # 第一阻力位 [[12]]
                support = 2 * pivot - last_row['最高']     # 第一支撑位 [[12]]

                # 保存该周期数据
                latest = df.iloc[-1]
                stock_data[freq] = {
                    "period": freq,
                    "price": float(latest['收盘']),
                    "high_20": float(recent_high),
                    "low_20": float(recent_low),
                    "pivot_point": float(pivot),
                    "support": float(support),
                    "resistance": float(resistance),
                    "ma": {
                        "ma5": float(latest['MA5']) if pd.notna(latest['MA5']) else None,
                        "ma20": float(latest['MA20']) if pd.notna(latest['MA20']) else None,
                        "ma60": float(latest['MA60']) if pd.notna(latest['MA60']) else None
                    },
                    "macd": {
                        "dif": float(latest['MACD']),
                        "dea": float(latest['MACD_Signal']),
                        "hist": float(latest['MACD_Hist'])
                    },
                    "rsi": float(latest['RSI']),
                    "kdj": {
                        "k": float(latest['K']),
                        "d": float(latest['D']),
                        "j": float(latest['J'])
                    },
                    "boll": {
                        "upper": float(latest['BOLL_UPPER']),
                        "middle": float(latest['BOLL_MIDDLE']),
                        "lower": float(latest['BOLL_LOWER'])
                    }
                }

            all_metrics[code] = stock_data

        return {
            "success": True,
            "data": all_metrics,
            "timestamp": datetime.datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "message": str(e)
        }

@mcp.tool()
def get_lhb_analysis(date: str) -> Dict[str, Any]:
    """
    获取龙虎榜资金动向和活跃营业部数据。

    参数：
        date (str): 日期，格式 'YYYYMMDD'

    返回：
        dict: 包含每日活跃营业部等数据。
    """
    import akshare as ak
    try:
        # 获取每日活跃营业部数据 [[1]]
        yyb_df = ak.stock_lhb_hyyyb_em(start_date=date, end_date=date)  # 获取指定日期数据 [[3]]
        yyb_text = yyb_df.to_string() if not yyb_df.empty else "无活跃营业部数据"

        data_text = f"""
=== 每日活跃营业部 ===
{yyb_text}
        """.strip()

        return {
            "success": True,
            "data": {"text": data_text},
            "message": "LHB analysis data retrieved."
        }
    except Exception as e:
        return {
            "success": False,
            "data": {},
            "message": f"Error: {str(e)}"
        }

@mcp.tool()
def analyze_lhb_seats(date: str) -> Dict[str, Any]:
    """
    分析龙虎榜席位数据，获取机构和营业部的原始信息。

    参数：
        date (str): 日期，格式 'YYYYMMDD'

    返回：
        dict: 包含机构席位成交明细、机构席位追踪和营业部上榜统计的文本数据。
    """
    import akshare as ak
    try:
        # 获取机构席位成交明细 (接口已更名)
        # 根据搜索结果，旧接口 stock_sina_lhb_jgmx 已更改为 stock_lhb_jgmx_sina [[94]]
        jgmx_df = ak.stock_lhb_jgmx_sina()
        jgmx_text = jgmx_df.to_string() if not jgmx_df.empty else "无机构席位成交明细数据"

        # 获取机构席位追踪数据 (接口已更名)
        # 旧接口 stock_sina_lhb_jgzz 已更改为 stock_lhb_jgzz_sina [[108]]
        # 此接口提供最近5, 10, 30, 60天的机构席位追踪统计数据 [[3]]
        jgzz_df = ak.stock_lhb_jgzz_sina(recent_day="5")
        jgzz_text = jgzz_df.to_string() if not jgzz_df.empty else "无机构席位追踪数据"

        # 获取营业部上榜统计数据
        # 使用 ak.stock_lhb_hyyyb_em 接口获取东方财富网每日活跃营业部数据 [[9]]
        yyb_df = ak.stock_lhb_hyyyb_em()
        yyb_text = yyb_df.to_string() if not yyb_df.empty else "无营业部上榜统计数据"

        # 获取个股龙虎榜详情
        # 使用 ak.stock_lhb_stock_detail_em 接口获取个股龙虎榜详情数据 [[21]]
        # 注意：此接口可能需要股票代码(symbol)和日期(date)作为参数，此处获取最新数据作为示例
        # stock_detail_df = ak.stock_lhb_stock_detail_em(date=date) # 此用法可能需要调整
        # 由于参数不明确，暂时注释，避免错误
        # stock_detail_text = stock_detail_df.to_string() if not stock_detail_df.empty else "无个股龙虎榜详情数据"

        data_text = f"""
=== 机构席位成交明细 ===
{jgmx_text}

=== 机构席位追踪 (最近5日) ===
{jgzz_text}

=== 营业部上榜统计 ===
{yyb_text}

# 注意：个股龙虎榜详情接口使用需进一步确认参数。
        """.strip()

        return {
            "success": True,
            "data": {"text": data_text},
            "message": "龙虎榜席位数据获取成功。"
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "message": f"获取数据时发生错误: {str(e)}"
        }

if __name__ == "__main__":
    mcp.run()