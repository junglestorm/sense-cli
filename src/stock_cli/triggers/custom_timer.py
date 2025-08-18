"""自定义定时器触发器示例"""

import asyncio
import logging
from typing import Tuple, Optional
from pathlib import Path

import typer
import yaml

from . import register
from ..core.config_resolver import resolve_triggers_path, load_triggers_config

logger = logging.getLogger(__name__)

@register("custom_timer")
def build_custom_timer(spec: dict) -> Tuple[str, str, Optional[str]]:
    """
    构造一个自定义定时任务
    
    Args:
        spec: 来自配置文件的触发器配置
        
    Returns:
        tuple: (role, content, task_template)
    """
    # 获取配置参数
    task_name = spec.get("task_name", "定时任务")
    task_description = spec.get("task_description", "执行定期检查")
    
    # 构造内容
    content = f"执行{task_name}: {task_description}"
    
    # 返回角色、内容和任务模板（可选）
    return ("scheduler", content, "periodic_check")


