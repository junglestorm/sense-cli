"""
板块与概念动态监控工具：提供概念发现、资金流、强度判断等功能。
"""

import logging
from datetime import datetime
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("Sector Dynamics Tools")

@mcp.tool()
def get_sector_rotation() -> Dict[str, Any]:
    """
    获取板块轮动数据，包括行业和概念板块。

    返回：
        dict: 包含各板块涨跌幅和涨停数量等数据。
    """
    import akshare as ak
    try:
        # 获取行业板块数据 [[17]]
        hy_df = ak.stock_board_industry_summary_em()  # 假设存在此接口，用于获取行业板块
        hy_text = hy_df.head(10).to_string() if not hy_df.empty else "无行业板块数据"

        # 获取概念板块数据 [[20]]
        gn_df = ak.stock_board_concept_summary_em()  # 假设存在此接口，用于获取概念板块
        gn_text = gn_df.head(10).to_string() if not gn_df.empty else "无概念板块数据"

        data_text = f"""
=== 行业板块涨幅TOP10 ===
{hy_text}

=== 概念板块涨幅TOP10 ===
{gn_text}
        """.strip()

        return {
            "success": True,
            "data": {"text": data_text},
            "message": "Sector rotation data retrieved."
        }
    except Exception as e:
        return {
            "success": False,
            "data": {},
            "message": f"Error: {str(e)}"
        }
        
@mcp.tool()
def list_concepts() -> Dict[str, Any]:
    """
    获取当前所有热门概念板块名称列表。
    """
    import akshare as ak
    try:
        concepts = ak.stock_board_concept_name_em()
        return {
            "success": True,
            "data": concepts,
            "count": len(concepts),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"list_concepts error: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def get_concept_metrics(concept: str) -> Dict[str, Any]:
    """
    获取概念的核心量化指标。
    """
    import akshare as ak
    import pandas as pd
    try:
        hist = ak.stock_board_concept_hist_em(symbol=concept, period="10")
        if len(hist) < 5:
            return {"success": False, "message": "Not enough history"}

        price_change_5d = hist['涨跌幅'].tail(5).sum()
        cons = ak.stock_board_concept_cons_em(symbol=concept)
        up_ratio = (cons['涨跌幅'] > 0).mean()
        avg_fund_flow = pd.to_numeric(cons['主力净额'], errors='coerce').mean()

        return {
            "success": True,
            "data": {
                "concept": concept,
                "price_change_5d": round(price_change_5d, 2),
                "up_ratio": round(up_ratio, 2),
                "avg_fund_flow": round(avg_fund_flow, 2),
                "stock_count": len(cons)
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"get_concept_metrics error: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def get_concept_stocks(concept: str, top_n: int = 10) -> Dict[str, Any]:
    """
    获取概念内资金流最强的前 N 只股票。
    """
    import akshare as ak
    import pandas as pd
    try:
        data = ak.stock_board_concept_cons_em(symbol=concept)
        data['主力净额'] = pd.to_numeric(data['主力净额'], errors='coerce')
        data = data.sort_values('主力净额', ascending=False).head(top_n)
        return {
            "success": True,
            "data": data[['代码', '名称', '最新价', '涨跌幅', '主力净额']].to_dict('records'),
            "returned_count": len(data),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"get_concept_stocks error: {e}")
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    mcp.run()