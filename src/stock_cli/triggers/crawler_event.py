"""爬虫事件触发器示例"""

import logging
from typing import Tuple, Optional

from . import register

logger = logging.getLogger(__name__)

@register("crawler_event")
def build_crawler_event(spec: dict) -> Tuple[str, str, Optional[str]]:
    """
    构造一个爬虫事件任务
    
    Args:
        spec: 来自配置文件的触发器配置
        
    Returns:
        tuple: (role, content, task_template)
    """
    # 获取配置参数
    url = spec.get("url", "https://example.com")
    target = spec.get("target", "网页内容")
    
    # 构造内容
    content = f"请分析从 {url} 抓取的 {target}"
    
    # 返回角色、内容和任务模板（可选）
    return ("crawler", content, "crawler_analysis")


# 模拟爬虫事件触发函数
def on_crawl_complete(data: dict, session_id: str = "default"):
    """
    当爬虫完成时调用此函数
    
    Args:
        data: 爬虫抓取的数据
        session_id: 会话ID
    """
    from . import TRIGGER_REGISTRY
    
    try:
        # 检查是否有注册的crawler_event触发器
        if "crawler_event" in TRIGGER_REGISTRY:
            builder = TRIGGER_REGISTRY["crawler_event"]
            role, content, task_template = builder({
                "url": data.get("url", ""),
                "target": data.get("target", "数据")
            })
            
            # 这里应该调用通用事件入口
            # 注意：实际实现中需要通过API或命令行调用trigger命令
            logger.info(f"触发爬虫事件: {role} - {content}")
            
    except Exception as e:
        logger.error(f"触发爬虫事件时出错: {e}")