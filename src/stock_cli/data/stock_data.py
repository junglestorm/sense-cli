"""
真实数据获取模块 - 使用akshare获取股票数据
"""

import asyncio
import datetime as dt
import time
from typing import Any, Dict, List

try:
    import akshare as ak

    AKSHARE_AVAILABLE = True
except ImportError:
    AKSHARE_AVAILABLE = False
    print("错误: akshare未安装，股票数据功能不可用")

try:
    import pandas as pd

    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False
    print("警告: pandas未安装，部分功能受限")


class RealStockData:
    """真实股票数据获取器"""

    def __init__(self):
        self.cache = {}
        self.cache_expire = 30  # 缓存30秒
        self.last_update = {}

    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self.last_update:
            return False
        return time.time() - self.last_update[key] < self.cache_expire

    async def get_index_realtime(self) -> List[Dict[str, Any]]:
        """获取实时指数数据"""
        cache_key = "index_realtime"

        if self._is_cache_valid(cache_key):
            return self.cache.get(cache_key, [])

        # 强制尝试akshare，不依赖全局AK_OK变量
        print("🔄 尝试获取akshare实时指数数据...")
        try:
            # 动态导入akshare
            import akshare as ak

            print("✅ akshare模块导入成功")

            # 获取实时指数数据
            df = await asyncio.get_event_loop().run_in_executor(
                None, ak.stock_zh_index_spot_em
            )
            print(f"✅ akshare返回{len(df)}条指数数据")

            # 筛选主要指数
            target_codes = ["000001", "399001", "399006", "000688"]
            target_names = ["上证指数", "深证成指", "创业板指", "科创50"]

            result = []
            for i, code in enumerate(target_codes):
                try:
                    row_data = df[df["代码"] == code]
                    if not row_data.empty:
                        row = row_data.iloc[0]
                        result.append(
                            {
                                "代码": code,
                                "名称": target_names[i],
                                "最新价": float(row["最新价"]),
                                "涨跌额": float(row["涨跌额"]),
                                "涨跌幅": float(row["涨跌幅"]),
                                "成交量": int(row["成交量"]),
                                "成交额": float(row["成交额"]),
                                "振幅": float(row["振幅"]),
                                "最高": float(row["最高"]),
                                "最低": float(row["最低"]),
                                "今开": float(row["今开"]),
                                "昨收": float(row["昨收"]),
                            }
                        )
                except Exception as e:
                    print(f"处理指数{code}数据失败: {e}")
                    continue

            if result:
                self.cache[cache_key] = result
                self.last_update[cache_key] = time.time()
                print(f"✅ 成功获取{len(result)}个指数的实时数据")
                return result
            else:
                print("⚠️ akshare数据为空")
                return []

        except ImportError:
            print("❌ akshare未安装")
            return []
        except Exception as e:
            print(f"❌ 获取akshare指数数据失败: {e}")
            return []

    async def get_hot_stocks(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取热门股票数据"""
        cache_key = f"hot_stocks_{limit}"

        if self._is_cache_valid(cache_key):
            return self.cache.get(cache_key, [])

        if not AKSHARE_AVAILABLE:
            print("⚠️ akshare不可用")
            return []

        try:
            # 获取A股实时数据
            print("🔄 正在获取A股实时数据...")
            df = await asyncio.get_event_loop().run_in_executor(
                None, ak.stock_zh_a_spot_em
            )

            if df is None or df.empty:
                print("⚠️ akshare返回空数据")
                return []

            # 按成交额排序，取前N只
            df_sorted = df.nlargest(limit, "成交额")

            result = []
            for _, row in df_sorted.iterrows():
                try:
                    result.append(
                        {
                            "代码": str(row["代码"]),
                            "名称": str(row["名称"])[:8],  # 限制长度
                            "最新价": float(row["最新价"]),
                            "涨跌额": float(row["涨跌额"]),
                            "涨跌幅": float(row["涨跌幅"]),
                            "成交量": int(row["成交量"]),
                            "成交额": float(row["成交额"]),
                            "换手率": (
                                float(row["换手率"])
                                if (PANDAS_OK and pd.notnull(row["换手率"]))
                                else 0
                            ),
                            "量比": (
                                float(row["量比"])
                                if (PANDAS_OK and pd.notnull(row["量比"]))
                                else 0
                            ),
                            "市盈率": (
                                float(row["市盈率-动态"])
                                if (PANDAS_OK and pd.notnull(row["市盈率-动态"]))
                                else 0
                            ),
                            "市净率": (
                                float(row["市净率"])
                                if (PANDAS_OK and pd.notnull(row["市净率"]))
                                else 0
                            ),
                        }
                    )
                except Exception as e:
                    print(f"处理股票数据失败: {e}")
                    continue

            if result:
                self.cache[cache_key] = result
                self.last_update[cache_key] = time.time()
                print(f"✅ 成功获取{len(result)}只热门股票数据")
                return result
            else:
                print("⚠️ 处理后数据为空")
                return []

        except Exception as e:
            print(f"❌ 获取akshare股票数据失败: {e}")
            return []

    async def get_kline_data(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = None,
        end_date: str = None,
    ) -> List[Dict[str, Any]]:
        """获取K线数据"""
        cache_key = f"kline_{symbol}_{period}"

        if self._is_cache_valid(cache_key):
            return self.cache.get(cache_key, [])

        if not AKSHARE_AVAILABLE:
            print("⚠️ akshare不可用")
            return []

        try:
            # 设置默认日期范围
            if not end_date:
                end_date = dt.datetime.now().strftime("%Y%m%d")
            if not start_date:
                start_dt = dt.datetime.now() - dt.timedelta(days=60)  # 增加到60天
                start_date = start_dt.strftime("%Y%m%d")

            print(f"🔄 正在获取 {symbol} 的K线数据 ({start_date} - {end_date})")

            # 获取K线数据
            if symbol.startswith(("60", "000", "002", "300", "688")):
                # A股股票
                df = await asyncio.get_event_loop().run_in_executor(
                    None,
                    ak.stock_zh_a_hist,
                    symbol,
                    period,
                    start_date,
                    end_date,
                    "qfq",
                )
            else:
                # 指数
                df = await asyncio.get_event_loop().run_in_executor(
                    None, ak.stock_zh_index_daily_em, symbol
                )
                if df is not None and not df.empty:
                    df = df.tail(30)  # 最近30天

            if df is None or df.empty:
                print(f"⚠️ {symbol} K线数据为空")
                return []

            result = []
            for _, row in df.iterrows():
                try:
                    # 处理日期格式
                    date_val = row["日期"]
                    if hasattr(date_val, "strftime"):
                        date_str = date_val.strftime("%Y-%m-%d")
                    else:
                        date_str = str(date_val)[:10]  # 取前10个字符

                    result.append(
                        {
                            "date": date_str,
                            "open": float(row["开盘"]),
                            "high": float(row["最高"]),
                            "low": float(row["最低"]),
                            "close": float(row["收盘"]),
                            "volume": int(row["成交量"]) if "成交量" in row else 0,
                        }
                    )
                except Exception as e:
                    print(f"处理K线数据行失败: {e}")
                    continue

            if result:
                self.cache[cache_key] = result
                self.last_update[cache_key] = time.time()
                print(f"✅ 成功获取{symbol} K线数据 {len(result)}条记录")
                return result
            else:
                print(f"⚠️ {symbol} K线数据处理后为空")
                return []

        except Exception as e:
            print(f"❌ 获取{symbol} K线数据失败: {e}")
            return []


# 全局数据获取器实例
stock_data = RealStockData()
