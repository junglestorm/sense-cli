from mcp.server.fastmcp import FastMCP
import logging

# 仅调整本模块与相关MCP模块的日志级别，避免影响全局 root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)

for name in ["mcp", "mcp.server", "mcp.server.fastmcp", "mcp.server.lowlevel"]:
    lg = logging.getLogger(name)
    lg.setLevel(logging.CRITICAL)
    lg.propagate = False

# 创建服务器
mcp = FastMCP("RAG Server")


@mcp.tool()
async def search_documents(query: str, top_k: int = 5) -> dict:
    """
    在RAG数据库中搜索相关文档
    
    参数:
        query (str): 搜索查询语句
        top_k (int): 返回结果数量（默认值：5）
        
    返回:
        dict: 包含相关文档的搜索结果
    """
    try:
        # 动态导入RAG模块，避免启动时依赖
        import sys
        import os
        # 获取当前文件的目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建项目根目录路径
        project_root = os.path.join(current_dir, '..', '..', '..')
        # 添加到Python路径
        sys.path.insert(0, project_root)
        
        # 导入RAG模块
        from stock_cli.core.rag import get_rag_instance, Document
        
        # 获取RAG实例
        rag = await get_rag_instance()
        if not rag:
            return {
                "error": "RAG系统不可用",
                "query": query,
                "results": [],
                "top_k": top_k
            }
        
        # 搜索相关文档
        documents: list[Document] = await rag.retrieve(query, top_k)
        
        # 格式化结果
        results = []
        for doc in documents:
            results.append({
                "id": doc.id,
                "content": doc.content,
                "metadata": doc.metadata
            })
        
        return {
            "query": query,
            "results": results,
            "top_k": top_k,
            "message": "成功检索到相关文档" if results else "未找到相关文档"
        }
    except Exception as e:
        return {
            "error": str(e),
            "query": query,
            "results": [],
            "top_k": top_k
        }


if __name__ == "__main__":
    mcp.run()