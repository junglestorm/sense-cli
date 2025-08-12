"""
核心工具模块：包含基础功能工具，例如健康检查、系统信息、计算工具等。
"""

import logging
from datetime import datetime
from typing import Dict, Any, List
import platform
import psutil
import statistics

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("Local Core Server")

@mcp.tool()
def health_check() -> Dict[str, Any]:
    """
    健康检查：返回服务可用状态与时间戳
    """
    return {
        "success": True,
        "name": "Local Core Server",
        "timestamp": datetime.now().isoformat(),
    }

@mcp.tool()
def system_info() -> Dict[str, Any]:
    """
    获取系统信息，包括操作系统、处理器、内存等。
    """
    try:
        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "processor": platform.processor(),
            "cpu_count": psutil.cpu_count(logical=True),
            "memory": psutil.virtual_memory()._asdict(),
        }
        return {"success": True, "data": info, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"system_info error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def disk_usage() -> Dict[str, Any]:
    """
    获取磁盘使用情况。
    """
    try:
        usage = psutil.disk_usage('/')
        return {
            "success": True,
            "data": {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"disk_usage error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def uptime() -> Dict[str, Any]:
    """
    获取系统运行时间。
    """
    try:
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime_duration = datetime.now() - boot_time
        return {
            "success": True,
            "data": {
                "boot_time": boot_time.isoformat(),
                "uptime": str(uptime_duration),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"uptime error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def calculate_average(numbers: List[float]) -> Dict[str, Any]:
    """
    计算一组数字的平均值。

    参数：
        numbers (List[float]): 数字列表。

    返回：
        dict: 包含成功状态和平均值。
    """
    try:
        avg = statistics.mean(numbers)
        return {"success": True, "average": avg, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"calculate_average error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def calculate_median(numbers: List[float]) -> Dict[str, Any]:
    """
    计算一组数字的中位数。

    参数：
        numbers (List[float]): 数字列表。

    返回：
        dict: 包含成功状态和中位数。
    """
    try:
        med = statistics.median(numbers)
        return {"success": True, "median": med, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"calculate_median error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def calculate_standard_deviation(numbers: List[float]) -> Dict[str, Any]:
    """
    计算一组数字的标准差。

    参数：
        numbers (List[float]): 数字列表。

    返回：
        dict: 包含成功状态和标准差。
    """
    try:
        std_dev = statistics.stdev(numbers)
        return {"success": True, "standard_deviation": std_dev, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"calculate_standard_deviation error: {e}")
        return {"success": False, "message": str(e)}

@mcp.tool()
def calculate_percentage_change(old_value: float, new_value: float) -> Dict[str, Any]:
    """
    计算两个值之间的百分比变化。

    参数：
        old_value (float): 原始值。
        new_value (float): 新值。

    返回：
        dict: 包含成功状态和百分比变化。
    """
    try:
        if old_value == 0:
            raise ValueError("Old value cannot be zero for percentage change calculation.")
        percentage_change = ((new_value - old_value) / old_value) * 100
        return {"success": True, "percentage_change": percentage_change, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"calculate_percentage_change error: {e}")
        return {"success": False, "message": str(e)}

if __name__ == "__main__":
    mcp.run()