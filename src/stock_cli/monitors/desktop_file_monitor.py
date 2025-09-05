import os
import time
import asyncio
import logging
from typing import Dict, Any, Set
import pymupdf4llm as pdf
from ..core.monitor_manager import Monitor, get_monitor_manager
from ..core.rag import get_rag_instance, Document
from ..utils.redis_bus import RedisBus

logger = logging.getLogger(__name__)

# 跨平台桌面路径
import sys
if sys.platform == 'win32':
    DESKTOP_PATH = os.path.join(os.environ['USERPROFILE'], 'Desktop')
else:
    DESKTOP_PATH = os.path.expanduser('~/Desktop')

# 只支持pdf、doc、docx文件类型
SUPPORTED_EXTS = {'.pdf', '.doc', '.docx','.txt','pptx','xlsx'}
SCAN_INTERVAL = 10  # 秒

async def scan_desktop_files() -> Set[str]:
    """获取桌面目录下所有支持的文件路径集合"""
    files = set()
    for fname in os.listdir(DESKTOP_PATH):
        fpath = os.path.join(DESKTOP_PATH, fname)
        if os.path.isfile(fpath) and os.path.splitext(fname)[1].lower() in SUPPORTED_EXTS:
            files.add(fpath)
    return files

async def add_file_to_rag(file_path: str, target_session: str) -> bool:
    """添加单个文件到RAG数据库"""
    try:
        rag_instance = await get_rag_instance()
        if not rag_instance:
            logger.warning("RAG实例不可用，无法添加文件: %s", file_path)
            return False
        
        # 读取文件内容
        content = ""
        try:
            # 统一用PyMuPDF读取所有支持的文件类型
            try:
                content: str = pdf.to_markdown(file_path) # 读取为markdown文本
            except ImportError:
                logger.warning("缺少PyMuPDF库，无法处理文件: %s", file_path)
                return False
            except Exception as e:
                logger.warning("用PyMuPDF读取文件失败: %s, 错误: %s", file_path, e)
                return False
        except Exception as e:
            logger.error("读取文件失败: %s, 错误: %s", file_path, e)
            return False
        
        # 创建Document对象
        document = Document(
            id=file_path,
            content=content,
            metadata={
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "file_size": os.path.getsize(file_path),
                "modified_time": os.path.getmtime(file_path)
            }
        )
        
        # 添加文档到RAG
        success = await rag_instance.add_documents([document])
        if success:
            logger.info("成功添加文件到RAG: %s", file_path)
        else:
            logger.warning("添加文件失败: %s", file_path)
        
        return success
        
    except Exception as e:
        logger.error("添加文件异常: %s, 错误: %s", file_path, e)
        return False

async def desktop_file_monitor_task(arguments: Dict[str, Any]):
    """桌面文件监控任务实现"""
    target_session = arguments.get("target_session", "default")
    
    logger.info("启动桌面文件监控器: target_session=%s", target_session)
    
    # 发送开始扫描消息到总线
    try:
        await RedisBus._ensure_client()
        await RedisBus.publish_message(
            "desktop_monitor",
            target_session,
            "开始扫描桌面文件并建立RAG文档",
            {"type": "rag_start"}
        )
    except Exception as e:
        logger.warning("发送开始消息失败: %s", e)
    
    known_files = await scan_desktop_files()
    
    # 初始化时添加所有现有文件
    success_count = 0
    total_count = len(known_files)
    
    for file_path in known_files:
        if await add_file_to_rag(file_path, target_session):
            success_count += 1
    
    # 所有文件处理完成后发送成功消息
    if total_count > 0:
        await RedisBus.publish_message(
            "desktop_monitor",
            target_session,
            f"RAG文档建立完成: 成功添加 {success_count}/{total_count} 个文件",
            {"type": "rag_complete", "success_count": success_count, "total_count": total_count}
        )
    
    while True:
        await asyncio.sleep(SCAN_INTERVAL)
        current_files = await scan_desktop_files()
        new_files = current_files - known_files
        
        if new_files:
            success_count = 0
            total_count = len(new_files)
            
            for file_path in new_files:
                if await add_file_to_rag(file_path, target_session):
                    success_count += 1
            
            # 新文件处理完成后发送成功消息
            await RedisBus.publish_message(
                "desktop_monitor",
                target_session,
                f"RAG文档建立完成: 成功添加 {success_count}/{total_count} 个新文件",
                {"type": "rag_complete", "success_count": success_count, "total_count": total_count}
            )
        
        known_files = current_files

async def desktop_file_monitor(arguments: Dict[str, Any]):
    """监控桌面文件变化并自动添加新文件到RAG数据库"""
    # 使用create_task启动监控任务
    task = asyncio.create_task(desktop_file_monitor_task(arguments))
    
    try:
        await task
    except asyncio.CancelledError:
        logger.info("桌面文件监控器被取消")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    except Exception as e:
        logger.error("桌面文件监控器异常: %s", e)
        raise

async def register_desktop_file_monitor():
    """注册桌面文件监控器"""
    manager = await get_monitor_manager()
    
    desktop_file_monitor_def = Monitor(
        name="desktop_file_monitor",
        description="监控桌面文件变化并自动添加到RAG数据库（支持PDF、DOC、DOCX）",
        parameters={
            "target_session": "目标会话ID"
        },
        start_func=desktop_file_monitor
    )
    
    manager.register_monitor(desktop_file_monitor_def)
    logger.info("注册desktop_file_monitor监控器完成")
    return desktop_file_monitor_def
