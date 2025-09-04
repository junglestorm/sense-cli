from mcp.server.fastmcp import FastMCP
import logging
import os
import chromadb
from chromadb.config import Settings
import httpx
from typing import List, Dict, Any, Optional
import asyncio

# 仅调整本模块与相关MCP模块的日志级别，避免影响全局 root logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)

for name in ["mcp", "mcp.server", "mcp.server.fastmcp", "mcp.server.lowlevel"]:
    lg = logging.getLogger(name)
    lg.setLevel(logging.CRITICAL)
    lg.propagate = False

# 创建服务器
mcp = FastMCP("RAG Server")

# 全局向量数据库实例
_vector_store = None
_ollama_base_url = "http://localhost:11434"
_ollama_model = "nomic-embed-text"

def _init_vector_store():
    """初始化向量数据库"""
    global _vector_store
    try:
        vector_store_path = "data/db/rag_vector_store"
        os.makedirs(vector_store_path, exist_ok=True)
        
        vector_store_client = chromadb.PersistentClient(
            path=vector_store_path,
            settings=Settings(allow_reset=True, anonymized_telemetry=False),
        )
        
        _vector_store = vector_store_client.get_or_create_collection(
            name="stock_rag", metadata={"hnsw:space": "cosine"}
        )
        
        logger.info(f"向量数据库已初始化: {vector_store_path}")
    except Exception as e:
        logger.error(f"初始化向量数据库失败: {str(e)}")
        _vector_store = None

async def _get_ollama_embedding(text: str) -> List[float]:
    """获取Ollama嵌入"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{_ollama_base_url}/api/embeddings",
                json={
                    "model": _ollama_model,
                    "prompt": text
                },
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return result["embedding"]
    except Exception as e:
        logger.error(f"获取Ollama嵌入失败: {str(e)}")
        raise

@mcp.tool()
async def search_documents(query: str, top_k: int = 5) -> dict:
    """
    在RAG数据库中搜索相关片段（由RAG内部切割），不做任何分段处理
    参数:
        query (str): 搜索查询语句
        top_k (int): 返回片段数量（默认值：5）
    返回:
        dict: 包含相关片段的搜索结果
    """
    try:
        # 初始化向量数据库
        if _vector_store is None:
            _init_vector_store()
        
        if not _vector_store:
            return {
                "error": "向量数据库不可用",
                "query": query,
                "results": [],
                "top_k": top_k
            }
            
        # 生成查询嵌入
        query_embedding = await _get_ollama_embedding(query)
        
        # 执行相似性搜索
        results = _vector_store.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        # 构造返回结果
        retrieved_docs = []
        for i in range(len(results['ids'][0])):
            doc = {
                "id": results['ids'][0][i],
                "content": results['documents'][0][i],
                "metadata": results['metadatas'][0][i] if results['metadatas'][0] else None
            }
            retrieved_docs.append(doc)
            
        return {
            "query": query,
            "results": retrieved_docs,
            "top_k": top_k,
            "message": "成功检索到相关片段" if retrieved_docs else "未找到相关片段"
        }
    except Exception as e:
        return {
            "error": str(e),
            "query": query,
            "results": [],
            "top_k": top_k
        }

@mcp.tool()
async def list_documents() -> dict:
    """
    列出RAG数据库中的所有文档
    
    返回:
        dict: 包含所有文档的列表和文档数量统计
    """
    try:
        # 初始化向量数据库
        if _vector_store is None:
            _init_vector_store()
        
        if not _vector_store:
            return {
                "error": "向量数据库不可用",
                "documents": [],
                "document_count": 0,
                "chunk_count": 0
            }
        
        # 获取所有文档
        results = _vector_store.get()
        
        # 统计文档数量（基于唯一文件路径）
        document_count = 0
        seen_files = set()
        
        # 构造返回结果
        documents = []
        for i in range(len(results['ids'])):
            metadata = results['metadatas'][i] if results['metadatas'] else {}
            file_path = metadata.get('file_path', '')
            
            # 统计唯一文档数量
            if file_path and file_path not in seen_files:
                seen_files.add(file_path)
                document_count += 1
            
            documents.append({
                "id": results['ids'][i],
                "content": results['documents'][i],
                "metadata": metadata
            })
        
        return {
            "success": True,
            "documents": documents,
            "document_count": document_count,
            "chunk_count": len(documents),
            "message": f"成功列出{document_count}个文档（{len(documents)}个分块）" if documents else "数据库中没有文档"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "documents": [],
            "document_count": 0,
            "chunk_count": 0
        }

if __name__ == "__main__":
    mcp.run()