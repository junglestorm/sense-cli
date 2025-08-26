"""
市场热度数据工具：获取当前市场成交额和换手率排名前N的股票。
"""

import logging
from typing import Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("Market Heat Data Tools")


@mcp.tool()
def get_top_volume_stocks(n: int = 50) -> Dict[str, Any]:
    """
    获取当前市场成交额排名前N的股票。

    参数：
        n (int): 获取排名前N的股票，默认为50。

    返回：
        dict: 包含排名前N的股票代码、名称和成交额的列表。
    """
    import akshare as ak
    from datetime import datetime
    try:
        # 获取所有A股实时行情数据
        df = ak.stock_zh_a_spot_em()
        
        # 按成交额降序排序并取前N条
        top_volume_df = df.sort_values(by='成交额', ascending=False).head(n)
        
        # 提取所需信息
        result = top_volume_df[['代码', '名称', '最新价', '成交额', '涨跌幅']].to_dict('records')
        
        return {
            "success": True,
            "data": result,
            "count": len(result),
            "rank_type": "volume",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


@mcp.tool()
def get_top_turnover_stocks(n: int = 50) -> Dict[str, Any]:
    """
    获取当前市场换手率排名前N的股票。

    参数：
        n (int): 获取排名前N的股票，默认为50。

    返回：
        dict: 包含排名前N的股票代码、名称和换手率的列表。
    """
    import akshare as ak
    from datetime import datetime
    try:
        # 获取所有A股实时行情数据
        df = ak.stock_zh_a_spot_em()
        
        # 按换手率降序排序并取前N条
        top_turnover_df = df.sort_values(by='换手率', ascending=False).head(n)
        
        # 提取所需信息
        result = top_turnover_df[['代码', '名称', '最新价', '换手率', '涨跌幅']].to_dict('records')
        
        return {
            "success": True,
            "data": result,
            "count": len(result),
            "rank_type": "turnover_rate",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    
    mcp.run()