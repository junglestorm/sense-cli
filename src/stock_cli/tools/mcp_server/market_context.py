"""
市场环境上下文工具：提供宏观市场风格、政策热度、全球联动等背景信息。
"""

import logging
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("Market Context Tools")


@mcp.tool()
def get_market_regime(date: str) -> Dict[str, Any]:
    """
    获取指定日期的涨停股池、炸板股池和跌停股池的关键数据。

    参数：
        date (str): 日期，格式 'YYYYMMDD'

    返回：
        dict: 包含股票名称列表和关键统计数据的字典。
    """
    import akshare as ak
    import pandas as pd
    try:
        # 获取涨停股池
        zt_pool = ak.stock_zt_pool_em(date=date)
        # 获取炸板股池
        zb_pool = ak.stock_zt_pool_dtgc_em(date=date)
        # 获取跌停股池
        dt_pool = ak.stock_zt_pool_tradedown_em(date=date)

        # 提取股票名称列表
        zt_names = zt_pool['名称'].tolist() if not zt_pool.empty else []
        zb_names = zb_pool['名称'].tolist() if not zb_pool.empty else []
        dt_names = dt_pool['名称'].tolist() if not dt_pool.empty else []

        # 计算关键统计数据
        zt_count = len(zt_names)
        zb_count = len(zb_names)
        dt_count = len(dt_names)
        avg_lianban = round(zt_pool['连板数'].mean(), 1) if not zt_pool.empty else 0.0

        # 格式化为纯文本数据返回
        data_text = f"""
涨停股票 ({zt_count}家):
{', '.join(zt_names) if zt_names else '无'}

炸板股票 ({zb_count}家):
{', '.join(zb_names) if zb_names else '无'}

跌停股票 ({dt_count}家):
{', '.join(dt_names) if dt_names else '无'}

市场统计数据:
- 涨停家数: {zt_count}
- 炸板家数: {zb_count}
- 跌停家数: {dt_count}
- 平均连板数: {avg_lianban}
        """.strip()

        return {
            "success": True,
            "data": {"text": data_text},
            "message": "Successfully retrieved market data."
        }

    except Exception as e:
        return {
            "success": False,
            "data": {},
            "message": f"An error occurred: {str(e)}"
        }

@mcp.tool()
def get_index_tech_analysis(date: str) -> Dict[str, Any]:
    """
    获取主要指数的技术分析关键数据。

    参数：
        date (str): 日期，格式 'YYYYMMDD'

    返回：
        dict: 包含指数技术指标的字典。
    """
    import akshare as ak
    try:
        # 获取上证指数日线数据
        index_data = ak.stock_zh_index_daily(symbol="sh000001")
        # 计算简单均线等（实际中可能需要更复杂的分析）
        latest_close = index_data['close'].iloc[-1]
        ma5 = index_data['close'].tail(5).mean()
        ma10 = index_data['close'].tail(10).mean()
        ma20 = index_data['close'].tail(20).mean()

        data_text = f"""
上证指数技术数据:
- 收盘点位: {latest_close:.2f}
- 5日均线: {ma5:.2f}
- 10日均线: {ma10:.2f}
- 20日均线: {ma20:.2f}
        """.strip()

        return {
            "success": True,
            "data": {"text": data_text},
            "message": "Index technical data retrieved."
        }
    except Exception as e:
        return {
            "success": False,
            "data": {},
            "message": f"Error: {str(e)}"
        }
        


@mcp.tool()
def get_global_context() -> Dict[str, Any]:
    """
    获取全球市场关键数据，并将结果格式化为文本字符串返回。
    """
    import akshare as ak
    import pandas as pd

    try:
        # --- 获取全球指数 ---
        global_index_df = ak.index_global_spot_em()
        spx_row = global_index_df[global_index_df['指数名称'] == '标普500']
        nasdaq_row = global_index_df[global_index_df['指数名称'] == '纳斯达克']
        dollar_index_row = global_index_df[global_index_df['指数名称'] == '美元指数']

        spx_price = float(spx_row['最新价'].iloc[0]) if not spx_row.empty else None
        nasdaq_price = float(nasdaq_row['最新价'].iloc[0]) if not nasdaq_row.empty else None
        dollar_index = float(dollar_index_row['最新价'].iloc[0]) if not dollar_index_row.empty else None

        # --- 获取外盘期货 ---
        futures_df = ak.futures_foreign_commodity_realtime()
        crude_row = futures_df[futures_df['名称'] == '原油']
        gold_row = futures_df[futures_df['名称'] == '黄金']

        crude_price = float(crude_row['最新价'].iloc[0]) if not crude_row.empty else None
        gold_price = float(gold_row['最新价'].iloc[0]) if not gold_row.empty else None

        # --- 获取比特币价格 ---
        bitcoin_df = ak.crypto_js_spot(symbol="BTC/USD")
        bitcoin_price = float(bitcoin_df['price'].iloc[-1]) if not bitcoin_df.empty else None

        # --- 获取10年期美国国债收益率 ---
        us_bond_df = ak.bond_investing_global(country="美国", index_name="美国10年期国债")
        us_10y_yield = float(us_bond_df['收盘'].iloc[-1]) if not us_bond_df.empty else None

        # --- 文本化拼接 ---
        data_text = f"""
全球市场关键数据 ({pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}):

【全球股指】
- 标普500指数: {spx_price:,.2f} 点
- 纳斯达克指数: {nasdaq_price:,.2f} 点

【金融指标】
- 美元指数: {dollar_index:.4f}
- 10年期美债收益率: {us_10y_yield:.4f}%

【大宗商品】
- 国际原油: ${crude_price:,.2f} /桶
- 国际黄金: ${gold_price:,.2f} /盎司

【加密货币】
- 比特币: ${bitcoin_price:,.2f} /BTC

数据来源: akshare 实时接口。
        """.strip()

        return {
            "success": True,
            "data": {"text": data_text},
            "message": "Successfully retrieved and formatted global market data."
        }

    except Exception as e:
        return {
            "success": False,
            "data": {"text": ""},
            "message": f"An error occurred: {str(e)}"
        }


if __name__ == "__main__":
    mcp.run()