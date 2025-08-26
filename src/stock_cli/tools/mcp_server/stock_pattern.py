"""
股票技术形态分析工具：识别“底部放量突破”和“高位横盘震荡”形态。
"""

import logging
from typing import Dict, Any, List

from mcp.server.fastmcp import FastMCP
import pandas as pd

logger = logging.getLogger(__name__)
mcp = FastMCP("Technical Pattern Analysis Tools")


@mcp.tool()
def analyze_stock_patterns(symbols: List[str], lookback_days: int = 90) -> Dict[str, Any]:
    """
    分析指定股票列表是否存在“底部放量突破”和“高位横盘震荡”两种形态。

    参数：
        symbols (List[str]): 股票代码列表，例如 ["600519", "000001"]。
        lookback_days (int): 回溯分析的天数，默认为90天。

    返回：
        dict: 包含每个股票的分析结果。
    """
    import akshare as ak
    from datetime import datetime

    try:
        # 初始化最终结果
        all_analysis_results = {}

        # 对列表中的每个股票进行分析
        for symbol in symbols:
            # 为每个股票创建独立的分析结果
            analysis_result = {
                "symbol": symbol,
                "analysis_date": datetime.now().isoformat(),
                "lookback_days": lookback_days,
                "patterns": {
                    "bottom_support_breakout": {"detected": False, "confidence": "low", "details": "Analysis failed or no data."},
                    "high_position_sideways": {"detected": False, "confidence": "low", "details": "Analysis failed or no data."}
                }
            }

            try:
                # 1. 获取历史数据
                df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq", 
                                    start_date=(pd.Timestamp.now() - pd.Timedelta(days=lookback_days*2)).strftime("%Y%m%d"))
                if df.empty or len(df) < lookback_days:
                    analysis_result["error"] = "Insufficient historical data"
                    all_analysis_results[symbol] = analysis_result
                    continue # 跳过当前股票，继续下一个

                # 确保数据按日期升序排列，并取最近的 lookback_days 天
                df = df.sort_values('日期').tail(lookback_days).reset_index(drop=True)
                df['日期'] = pd.to_datetime(df['日期'])

                # 计算辅助指标
                df['volume_ma_10'] = df['成交量'].rolling(window=10).mean() # 10日均量
                recent_close = df['收盘价'].iloc[-1]
                recent_volume = df['成交量'].iloc[-1]
                avg_volume = df['volume_ma_10'].iloc[-1]

                # 更新当前价格和成交量信息
                analysis_result["current_price"] = recent_close
                analysis_result["current_volume"] = recent_volume
                analysis_result["average_volume"] = avg_volume

                # 用于分析的近期数据
                recent_df = df.tail(20) # 分析最近20天的走势
                recent_highs = recent_df['最高价']
                recent_lows = recent_df['最低价']
                recent_closes = recent_df['收盘价']

                # ------------------------ 形态1: 底部支撑明显，放量突破 ------------------------
                # 假设底部区域：取过去一段时间的最低价作为支撑位
                support_zone_low = df['最低价'].min()
                support_zone_high = df['最低价'].quantile(0.25) # 用下四分位数定义支撑区间的上沿
                support_zone = f"{support_zone_low:.2f}-{support_zone_high:.2f}"

                # 判断近期是否在支撑区上方运行并向上突破
                breakout_threshold = support_zone_high * 1.05 # 突破支撑区上沿5%视为突破
                has_breakout = recent_close > breakout_threshold

                # 判断是否放量
                volume_spike = recent_volume > avg_volume * 1.8 # 当前成交量超过10日均量1.8倍

                # 综合判断
                if has_breakout and volume_spike and (recent_close > support_zone_high):
                    analysis_result["patterns"]["bottom_support_breakout"] = {
                        "detected": True,
                        "confidence": "high" if (recent_close / support_zone_high > 1.1 and recent_volume / avg_volume > 2.0) else "medium",
                        "details": f"股价从支撑区{support_zone}放量突破，当前价{recent_close:.2f}，成交量{recent_volume/1e8:.2f}亿。"
                    }
                else:
                    analysis_result["patterns"]["bottom_support_breakout"]["details"] = f"未满足放量突破条件。支撑区: {support_zone}, 当前价: {recent_close:.2f}"

                # ------------------------ 形态2: 高位横盘震荡 ------------------------
                # 判断是否处于“高位”：当前价格接近近期高点
                recent_high = df['最高价'].max()
                high_threshold = recent_high * 0.9 # 当前价在近期高点的90%以上视为高位
                is_at_high = recent_close >= high_threshold

                # 判断是否“横盘震荡”：价格波动率低，无趋势
                price_std = recent_closes.std() # 价格标准差
                price_mean = recent_closes.mean()
                volatility_ratio = price_std / price_mean # 相对波动率
                # 检查近期价格是否在一个窄幅区间内波动
                narrow_range = (recent_highs.max() - recent_lows.min()) / recent_lows.min() < 0.15 # 20天内最高最低差小于15%
                low_volatility = volatility_ratio < 0.05 # 相对波动率低于5%

                # 综合判断
                if is_at_high and narrow_range and low_volatility:
                    analysis_result["patterns"]["high_position_sideways"] = {
                        "detected": True,
                        "confidence": "medium",
                        "details": f"股价在高位{recent_lows.min():.2f}-{recent_highs.max():.2f}区间内窄幅震荡，接近近期高点{recent_high:.2f}。"
                    }
                else:
                    analysis_result["patterns"]["high_position_sideways"]["details"] = f"未满足高位横盘条件。高位: {is_at_high}, 窄幅: {narrow_range}"

            except Exception as e:
                # 捕获单个股票分析过程中的异常
                logger.warning(f"Error analyzing {symbol}: {str(e)}")
                analysis_result["error"] = str(e)

            # 将当前股票的分析结果存入总结果字典
            all_analysis_results[symbol] = analysis_result

        return {
            "success": True,
            "data": all_analysis_results,
            "total_analyzed": len(symbols),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error in batch analysis: {str(e)}")
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    
    mcp.run()
