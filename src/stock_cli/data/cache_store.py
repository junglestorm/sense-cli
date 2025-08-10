"""数据持久化与缓存层

作用:
1. 使用 SQLite 持久化 akshare 爬取到的真实数据, 避免每次重复抓取
2. 统一提供 get / set 接口并带 TTL 逻辑

表结构:
  stock_prices(symbol TEXT PRIMARY KEY, market TEXT, data_json TEXT, fetched_at INTEGER)
  stock_history(symbol TEXT, market TEXT, period TEXT, data_json TEXT, fetched_at INTEGER,
                PRIMARY KEY(symbol, market, period))
  market_overview(key TEXT PRIMARY KEY, data_json TEXT, fetched_at INTEGER)

所有时间使用 UNIX 时间戳秒.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional


class DataCache:
    def __init__(self, db_path: str = "data/db/market_cache.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """CREATE TABLE IF NOT EXISTS stock_prices(
                symbol TEXT PRIMARY KEY,
                market TEXT,
                data_json TEXT NOT NULL,
                fetched_at INTEGER NOT NULL
                )"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS stock_history(
                symbol TEXT,
                market TEXT,
                period TEXT,
                data_json TEXT NOT NULL,
                fetched_at INTEGER NOT NULL,
                PRIMARY KEY(symbol, market, period)
                )"""
            )
            cur.execute(
                """CREATE TABLE IF NOT EXISTS market_overview(
                key TEXT PRIMARY KEY,
                data_json TEXT NOT NULL,
                fetched_at INTEGER NOT NULL
                )"""
            )
            conn.commit()

    # -------- 通用内部工具 --------
    def _get_entry(self, table: str, where: str, params: tuple) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT data_json, fetched_at FROM {table} WHERE {where}", params)
            row = cur.fetchone()
            if not row:
                return None
            data_json, fetched_at = row
            try:
                data = json.loads(data_json)
            except Exception:
                data = None
            return {"data": data, "fetched_at": fetched_at}

    def _set_entry(self, table: str, columns: str, values: tuple):
        placeholders = ",".join(["?"] * len(values))
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
                values,
            )
            conn.commit()

    # -------- 价格 --------
    def get_price(self, symbol: str, ttl: int) -> Optional[Dict[str, Any]]:
        entry = self._get_entry("stock_prices", "symbol=?", (symbol,))
        if not entry:
            return None
        if time.time() - entry["fetched_at"] > ttl:
            return None
        return entry["data"]

    def set_price(self, symbol: str, market: str, data: Dict[str, Any]):
        self._set_entry(
            "stock_prices",
            "symbol, market, data_json, fetched_at",
            (symbol, market, json.dumps(data, ensure_ascii=False), int(time.time())),
        )

    # -------- 历史 --------
    def get_history(
        self, symbol: str, market: str, period: str, ttl: int
    ) -> Optional[Dict[str, Any]]:
        entry = self._get_entry(
            "stock_history", "symbol=? AND market=? AND period=?", (symbol, market, period)
        )
        if not entry:
            return None
        if time.time() - entry["fetched_at"] > ttl:
            return None
        return entry["data"]

    def set_history(self, symbol: str, market: str, period: str, data: Dict[str, Any]):
        self._set_entry(
            "stock_history",
            "symbol, market, period, data_json, fetched_at",
            (symbol, market, period, json.dumps(data, ensure_ascii=False), int(time.time())),
        )

    # -------- 概览 --------
    def get_market_overview(self, key: str, ttl: int) -> Optional[Dict[str, Any]]:
        entry = self._get_entry("market_overview", "key=?", (key,))
        if not entry:
            return None
        if time.time() - entry["fetched_at"] > ttl:
            return None
        return entry["data"]

    def set_market_overview(self, key: str, data: Dict[str, Any]):
        self._set_entry(
            "market_overview",
            "key, data_json, fetched_at",
            (key, json.dumps(data, ensure_ascii=False), int(time.time())),
        )


# 全局实例
cache = DataCache()

__all__ = ["cache", "DataCache"]
