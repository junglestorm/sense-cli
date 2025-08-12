"""
本地可运行的通用 MCP 服务器
替换原先的股票相关函数，提供无需外部网络依赖的本地工具，便于验证 MCP 调用链路
"""

import logging
from datetime import datetime
from typing import Dict, Any
import sys
from pathlib import Path
import time
import os

# 添加项目路径（与原实现一致，确保在项目根目录下可运行）
project_root = Path(__file__).resolve().parents[4]
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# 完全禁用 MCP 相关的控制台日志输出（避免污染 STDIO）
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

def setup_logging(log_path: str, level=logging.CRITICAL, max_bytes=5 * 1024 * 1024, backup_count=5):
    handler = RotatingFileHandler(log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger

logger = setup_logging("logs/mcp_stock_core.log")

# 创建 MCP 服务器
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("Local Core Server")

# =========================
# 本地工具（无需外网/第三方数据源）
# =========================

@mcp.tool()
def health_check() -> Dict[str, Any]:
    """
    健康检查：返回服务可用状态与时间戳
    """
    return {
        "success": True,
        "name": "Local Core Server",
        "cwd": os.getcwd(),
        "timestamp": datetime.now().isoformat(),
    }


@mcp.tool()
def echo(text: str) -> Dict[str, Any]:
    """
    回显文本
    Args:
        text: 任意字符串
    Returns:
        原样回显与长度信息
    """
    data = {
        "text": text,
        "length": len(text),
        "timestamp": datetime.now().isoformat(),
    }
    return {"success": True, "data": data}


@mcp.tool()
def add(a: float, b: float) -> Dict[str, Any]:
    """
    计算两个数的和
    Args:
        a: 数值
        b: 数值
    Returns:
        sum: a + b
    """
    try:
        s = float(a) + float(b)
        return {"success": True, "a": a, "b": b, "sum": s, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"add error: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def repeat(text: str, times: int = 1, sep: str = "") -> Dict[str, Any]:
    """
    重复拼接字符串
    Args:
        text: 文本
        times: 次数（非负整数）
        sep: 连接分隔符
    Returns:
        result: 拼接结果
    """
    try:
        t = int(times)
        if t < 0:
            raise ValueError("times must be non-negative")
        result = sep.join([text] * t) if t > 0 else ""
        return {"success": True, "result": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"repeat error: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def sleep_ms(ms: int = 100) -> Dict[str, Any]:
    """
    休眠指定毫秒
    Args:
        ms: 毫秒 (0-10000)
    Returns:
        elapsed_ms: 实际耗时（毫秒）
    """
    try:
        m = int(ms)
        if m < 0 or m > 10000:
            raise ValueError("ms must be in [0, 10000]")
        start = time.perf_counter()
        time.sleep(m / 1000.0)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return {"success": True, "elapsed_ms": elapsed_ms, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"sleep_ms error: {e}")
        return {"success": False, "message": str(e)}


@mcp.tool()
def env(var: str) -> Dict[str, Any]:
    """
    获取环境变量
    Args:
        var: 环境变量名
    Returns:
        value: 若不存在则为空字符串
    """
    try:
        value = os.getenv(var, "")
        return {"success": True, "var": var, "value": value, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"env error: {e}")
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    # 由 main.py 统一处理日志；此处仅启动服务器
    mcp.run()
