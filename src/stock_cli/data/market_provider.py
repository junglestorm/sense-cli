"""市场数据获取封装 (基于 akshare)"""

import asyncio
import datetime as dt
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import akshare as ak

    AK_OK = True
except ImportError as e:
    print(f"[MarketData] akshare导入失败: {e}")
    AK_OK = False

try:
    import pandas as pd

    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False


class MarketData:
    def __init__(self):
        self.indices = {
            "上证指数": "000001",
            "深证成指": "399001",
            "创业板指": "399006",
            "科创50": "000688",
        }
        self.hot_stocks = ["000858", "002594", "300750", "600519", "000002"]
        self.cache_data: Dict[str, Any] = {}
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.cache_file = self.data_dir / "market_cache.json"
        self._load_cache()

    # --------------- 缓存 ---------------
    def _is_cache_valid(self, key: str, expire: int) -> bool:
        entry = self.cache_data.get(key)
        if not entry:
            return False
        return time.time() - entry.get("timestamp", 0) < expire

    def _get_cache(self, key: str):
        entry = self.cache_data.get(key)
        return entry and entry.get("data")

    def _set_cache(self, key: str, data: Any):
        self.cache_data[key] = {"timestamp": time.time(), "data": data}
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.cache_data, f, ensure_ascii=False)
        except Exception:
            pass

    def _load_cache(self):
        if not self.cache_file.exists():
            return
        try:
            self.cache_data = json.loads(self.cache_file.read_text(encoding="utf-8"))
        except Exception:
            self.cache_data = {}

    # --------------- 指数数据 ---------------
    async def get_index_data(self) -> List[Dict[str, Any]]:
        key = "index_data"
        if self._is_cache_valid(key, 30):
            cached = self._get_cache(key)
            if cached:
                return cached
        if not AK_OK:
            return []
        data: List[Dict[str, Any]] = []
        try:
            tasks = [
                asyncio.create_task(self._fetch_single_index(name, code))
                for name, code in self.indices.items()
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, dict):
                    data.append(r)
            if data:
                self._set_cache(key, data)
        except Exception as e:
            print(f"[get_index_data] 获取指数数据异常: {e}")
        return data

    async def _fetch_single_index(self, name: str, code: str) -> Optional[Dict[str, Any]]:
        try:
            df = await asyncio.get_event_loop().run_in_executor(None, ak.stock_zh_index_spot)
            part = df[df["代码"] == code]
            if part.empty:
                return None
            row = part.iloc[0]
            return {
                "代码": code,
                "名称": name,
                "最新价": f"{row['最新价']:.2f}",
                "涨跌额": f"{row['涨跌额']:.2f}",
                "涨跌幅": f"{row['涨跌幅']:.2f}%",
                "成交量": f"{row['成交量']/10000:.0f}万手",
                "成交额": f"{row['成交额']/100000000:.2f}亿",
                "振幅": f"{row['振幅']:.2f}%",
                "最高": f"{row['最高']:.2f}",
                "最低": f"{row['最低']:.2f}",
                "今开": f"{row['今开']:.2f}",
                "昨收": f"{row['昨收']:.2f}",
            }
        except Exception as e:
            print(f"[_fetch_single_index] 获取单指数数据异常({name}-{code}): {e}")
            return None

    # --------------- 热门股票 ---------------
    async def get_hot_stocks(self, limit: int = 15) -> List[Dict[str, Any]]:
        key = f"hot_{limit}"
        if self._is_cache_valid(key, 60):
            c = self._get_cache(key)
            if c:
                return c
        if not AK_OK:
            return []
        try:
            df = await asyncio.get_event_loop().run_in_executor(None, ak.stock_hot_follow_xq)
            hot = df.head(limit)
            data = []
            for _, row in hot.iterrows():
                data.append(
                    {
                        "代码": row["代码"],
                        "名称": row["名称"][:8],
                        "最新价": f"{row['最新价']:.2f}",
                        "涨跌额": f"{row['涨跌额']:.2f}",
                        "涨跌幅": f"{row['涨跌幅']:.2f}%",
                        "成交量": f"{row['成交量']/10000:.0f}万",
                        "换手率": (
                            f"{row['换手率']:.2f}%"
                            if PANDAS_OK and pd.notnull(row["换手率"])
                            else "-"
                        ),
                        "量比": (
                            f"{row['量比']:.2f}" if PANDAS_OK and pd.notnull(row["量比"]) else "-"
                        ),
                    }
                )
            if data:
                self._set_cache(key, data)
            return data
        except Exception as e:
            print(f"[get_hot_stocks] 获取热门股票异常: {e}")
            return []

    # --------------- 市场概览 ---------------
    async def get_market_summary(self) -> Dict[str, Any]:
        key = "market_summary"
        if self._is_cache_valid(key, 60):
            c = self._get_cache(key)
            if c:
                return c
        if not AK_OK:
            return {}
        try:
            df = await asyncio.get_event_loop().run_in_executor(None, ak.stock_zh_a_spot)
            total = len(df)
            rising = len(df[df["涨跌幅"] > 0])
            falling = len(df[df["涨跌幅"] < 0])
            unchanged = len(df[df["涨跌幅"] == 0])
            avg_change = df["涨跌幅"].mean()
            result = {
                "总股票数": total,
                "上涨家数": rising,
                "下跌家数": falling,
                "平盘家数": unchanged,
                "平均涨跌幅": f"{avg_change:.2f}%",
                "上涨比例": f"{rising/total*100:.1f}%",
                "更新时间": dt.datetime.now().strftime("%H:%M:%S"),
            }
            self._set_cache(key, result)
            return result
        except Exception as e:
            print(f"[get_market_summary] 获取市场概览异常: {e}")
            return {}

    async def get_economic_news(self) -> List[Dict[str, Any]]:
        key = "economic_news"
        if self._is_cache_valid(key, 60):
            c = self._get_cache(key)
            if c:
                return c
        if not AK_OK:
            return []
        try:
            df = await asyncio.get_event_loop().run_in_executor(None, ak.news_economic_baidu)
            data = []
            for _, row in df.iterrows():
                data.append(
                    {
                        "标题": row["标题"],
                        "发布时间": row["发布时间"],
                        "来源": row["来源"],
                        "链接": row["链接"],
                    }
                )
            if data:
                self._set_cache(key, data)
            return data
        except Exception as e:
            print(f"[get_economic_news] 获取经济新闻异常: {e}")
            return []


__all__ = ["MarketData"]

if __name__ == "__main__":
    import asyncio
    from datetime import datetime

    async def run_tests():
        provider = MarketData()
        print(f"\n[{datetime.now().isoformat()}] 测试 get_index_data")
        indices = await provider.get_index_data()
        print("指数数据示例:", indices or "无数据")

        print(f"\n[{datetime.now().isoformat()}] 测试 get_hot_stocks")
        stocks = await provider.get_hot_stocks()
        print("热门股票示例:", stocks or "无数据")

        print(f"\n[{datetime.now().isoformat()}] 测试 get_market_summary")
        summary = await provider.get_market_summary()
        print("市场概览示例:", summary or "无数据")

    asyncio.run(run_tests())
