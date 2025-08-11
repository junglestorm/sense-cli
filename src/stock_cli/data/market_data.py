"""行情数据服务模块"""

import asyncio
import datetime as dt
import json
import time
from collections import deque
from pathlib import Path
from typing import Any, Dict, List

try:
    import akshare as ak

    AK_OK = True
except ImportError:
    AK_OK = False

try:
    import pandas as pd

    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False


class MarketData:
    """实时行情数据获取器"""

    def __init__(self):
        self.indices = {
            "上证指数": "000001",
            "深证成指": "399001",
            "创业板指": "399006",
            "科创50": "000688",
        }
        self.hot_stocks = ["000858", "002594", "300750", "600519", "000002"]
        self.cache_time = 0
        self.cache_data = {}
        self.history_data = deque(maxlen=100)
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        self.cache_file = self.data_dir / "market_cache.json"
        self.load_cache()

    def load_cache(self):
        """从文件加载缓存数据"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    self.cache_data = cache_data.get("data", {})
                    self.cache_time = cache_data.get("timestamp", 0)
        except Exception as e:
            print(f"加载缓存失败: {e}")
            self.cache_data = {}
            self.cache_time = 0

    def save_cache(self):
        """保存缓存数据到文件"""
        try:
            cache_data = {"timestamp": self.cache_time, "data": self.cache_data}
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存缓存失败: {e}")

    def is_cache_valid(self, cache_key: str, expire_seconds: int = 60) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self.cache_data:
            return False

        cache_entry = self.cache_data[cache_key]
        timestamp = cache_entry.get("timestamp", 0)
        return time.time() - timestamp < expire_seconds

    def get_cached_data(self, cache_key: str):
        """获取缓存数据"""
        if cache_key in self.cache_data:
            return self.cache_data[cache_key].get("data")
        return None

    def set_cached_data(self, cache_key: str, data):
        """设置缓存数据"""
        self.cache_data[cache_key] = {"timestamp": time.time(), "data": data}
        self.save_cache()

    async def get_index_data(self) -> List[Dict[str, Any]]:
        """获取指数实时数据（仅返回名称与最新价）。"""
        cache_key = "index_data"

        if self.is_cache_valid(cache_key, expire_seconds=25):
            cached_data = self.get_cached_data(cache_key)
            if cached_data:
                return cached_data

        if not AK_OK:
            return []

        try:
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(None, ak.stock_zh_index_spot_em)
            data: List[Dict[str, Any]] = []
            if df is not None and not df.empty:
                for name, code in self.indices.items():
                    row = None
                    try:
                        by_code = df[df["代码"] == code]
                        if not by_code.empty:
                            row = by_code.iloc[0]
                        else:
                            by_name = df[df["名称"] == name]
                            if not by_name.empty:
                                row = by_name.iloc[0]
                        if row is None:
                            continue
                        price = row.get("最新价", None)
                        if price is None:
                            continue
                        data.append({"名称": name, "最新价": f"{price:.2f}"})
                    except Exception:
                        continue
            if data:
                self.set_cached_data(cache_key, data)
            return data
        except Exception:
            cached_data = self.get_cached_data(cache_key)
            return cached_data or []

    # _fetch_single_index 已弃用（逻辑改为单次批量拉取）。

    async def get_hot_stocks_data(self) -> List[Dict[str, Any]]:
        """获取热门股票数据"""
        cache_key = "hot_stocks_data"

        if self.is_cache_valid(cache_key, expire_seconds=60):
            cached_data = self.get_cached_data(cache_key)
            if cached_data:
                return cached_data

        if not AK_OK:
            return []

        try:
            df = await asyncio.get_event_loop().run_in_executor(
                None, ak.stock_zh_a_spot_em
            )
            hot_data = df.head(20)

            data = []
            for _, row in hot_data.iterrows():
                data.append(
                    {
                        "代码": row["代码"],
                        "名称": row["名称"][:8],
                        "最新价": f"{row['最新价']:.2f}",
                        "涨跌额": f"{row['涨跌额']:.2f}",
                        "涨跌幅": f"{row['涨跌幅']:.2f}%",
                        "成交量": f"{row['成交量'] / 10000:.0f}万",
                        "换手率": f"{row['换手率']:.2f}%",
                        "量比": f"{row['量比']:.2f}",
                        "市盈率": (
                            f"{row['市盈率-动态']:.1f}"
                            if (PANDAS_OK and pd.notnull(row["市盈率-动态"]))
                            else "-"
                        ),
                        "市净率": (
                            f"{row['市净率']:.2f}"
                            if (PANDAS_OK and pd.notnull(row["市净率"]))
                            else "-"
                        ),
                    }
                )

            if data:
                self.set_cached_data(cache_key, data[:15])

            return data[:15]
        except Exception:
            cached_data = self.get_cached_data(cache_key)
            if cached_data:
                return cached_data
            return []

    async def get_market_summary(self) -> Dict[str, Any]:
        """获取市场总体数据"""
        cache_key = "market_summary"

        if self.is_cache_valid(cache_key, expire_seconds=60):
            cached_data = self.get_cached_data(cache_key)
            if cached_data:
                return cached_data

        if not AK_OK:
            return {}

        try:
            df = await asyncio.get_event_loop().run_in_executor(
                None, ak.stock_zh_a_spot_em
            )

            total_stocks = len(df)
            rising = len(df[df["涨跌幅"] > 0])
            falling = len(df[df["涨跌幅"] < 0])
            unchanged = len(df[df["涨跌幅"] == 0])

            avg_change = df["涨跌幅"].mean()
            total_volume = df["成交量"].sum() / 100000000
            total_amount = df["成交额"].sum() / 1000000000000

            result = {
                "总股票数": total_stocks,
                "上涨家数": rising,
                "下跌家数": falling,
                "平盘家数": unchanged,
                "平均涨跌幅": f"{avg_change:.2f}%",
                "总成交量": f"{total_volume:.2f}亿手",
                "总成交额": f"{total_amount:.2f}万亿",
                "上涨比例": f"{rising / total_stocks * 100:.1f}%",
                "更新时间": dt.datetime.now().strftime("%H:%M:%S"),
            }

            self.set_cached_data(cache_key, result)

            return result
        except Exception:
            cached_data = self.get_cached_data(cache_key)
            if cached_data:
                return cached_data
            return {}
