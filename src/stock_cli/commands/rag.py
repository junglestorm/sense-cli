"""RAG命令模块"""

import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from ..core.rag import get_rag_instance, Document

app = typer.Typer(help="RAG文档管理命令")
console = Console()


@app.command()
def add(
    content: str = typer.Argument(..., help="文档内容"),
    doc_id: Optional[str] = typer.Option(None, "--id", help="文档ID"),
    metadata: Optional[str] = typer.Option(None, "--metadata", help="文档元数据（JSON格式）")
):
    """添加文档到RAG系统"""
    async def _add():
        try:
            import json
            rag = await get_rag_instance()
            if not rag:
                console.print("[red]RAG系统不可用[/red]")
                return

            # 解析元数据
            meta = None
            if metadata:
                try:
                    meta = json.loads(metadata)
                except json.JSONDecodeError:
                    console.print("[yellow]元数据格式不正确，将忽略[/yellow]")

            # 创建文档
            document = Document(
                id=doc_id or content[:20],  # 使用内容前20个字符作为ID
                content=content,
                metadata=meta
            )

            # 添加文档
            success = await rag.add_documents([document])
            if success:
                console.print("[green]文档添加成功[/green]")
            else:
                console.print("[red]文档添加失败[/red]")
        except Exception as e:
            console.print(f"[red]添加文档时出错: {e}[/red]")

    asyncio.run(_add())


@app.command("add-file")
def add_file(
    file_path: str = typer.Argument(..., help="文档文件的绝对路径"),
    doc_id: Optional[str] = typer.Option(None, "--id", help="文档ID"),
    metadata: Optional[str] = typer.Option(None, "--metadata", help="文档元数据（JSON格式）")
):
    """通过文件路径添加文档到RAG系统"""
    async def _add_file():
        try:
            import json
            import os
            rag = await get_rag_instance()
            if not rag:
                console.print("[red]RAG系统不可用[/red]")
                return

            # 检查文件是否存在
            if not os.path.exists(file_path):
                console.print(f"[red]文件不存在: {file_path}[/red]")
                return

            # 读取文件内容
            try:
                # 检查文件扩展名
                _, ext = os.path.splitext(file_path)
                if ext.lower() == '.pdf':
                    # 尝试导入PyPDF2处理PDF文件
                    try:
                        import PyPDF2
                        with open(file_path, 'rb') as f:
                            pdf_reader = PyPDF2.PdfReader(f)
                            content = ""
                            for page in pdf_reader.pages:
                                content += page.extract_text() + "\n"
                    except ImportError:
                        console.print("[red]缺少PDF处理库，请安装PyPDF2: pip install PyPDF2[/red]")
                        return
                else:
                    # 处理文本文件
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
            except Exception as e:
                console.print(f"[red]读取文件失败: {e}[/red]")
                return

            # 解析元数据
            meta = None
            if metadata:
                try:
                    meta = json.loads(metadata)
                except json.JSONDecodeError:
                    console.print("[yellow]元数据格式不正确，将忽略[/yellow]")

            # 创建文档
            document = Document(
                id=doc_id or os.path.basename(file_path),  # 使用文件名作为ID
                content=content,
                metadata=meta
            )

            # 添加文档
            success = await rag.add_documents([document])
            if success:
                console.print("[green]文档添加成功[/green]")
            else:
                console.print("[red]文档添加失败[/red]")
        except Exception as e:
            console.print(f"[red]添加文档时出错: {e}[/red]")

    asyncio.run(_add_file())


@app.command()
def query(
    question: str = typer.Argument(..., help="查询问题"),
    top_k: int = typer.Option(3, "--top-k", help="返回结果数量")
):
    """查询RAG系统中的相关文档"""
    async def _query():
        try:
            rag = await get_rag_instance()
            if not rag:
                console.print("[red]RAG系统不可用[/red]")
                return

            # 执行查询
            documents = await rag.retrieve(question, top_k=top_k)
            
            if not documents:
                console.print("[yellow]未找到相关文档[/yellow]")
                return

            # 显示结果
            table = Table(title="检索结果")
            table.add_column("ID", style="cyan")
            table.add_column("内容", style="magenta")
            table.add_column("元数据", style="green")

            for doc in documents:
                meta_str = str(doc.metadata) if doc.metadata else ""
                table.add_row(doc.id, doc.content[:100] + "..." if len(doc.content) > 100 else doc.content, meta_str)

            console.print(table)
        except Exception as e:
            console.print(f"[red]查询文档时出错: {e}[/red]")

    asyncio.run(_query())


@app.command()
def list():
    """列出RAG数据库中的所有文档"""
    async def _list():
        try:
            rag = await get_rag_instance()
            if not rag:
                console.print("[red]RAG系统不可用[/red]")
                return

            # 获取所有文档
            documents = await rag.get_all_documents()
            
            if not documents:
                console.print("[yellow]数据库中没有文档[/yellow]")
                return

            # 显示结果
            table = Table(title="所有文档")
            table.add_column("ID", style="cyan")
            table.add_column("内容", style="magenta")
            table.add_column("元数据", style="green")

            for doc in documents:
                meta_str = str(doc.metadata) if doc.metadata else ""
                table.add_row(doc.id, doc.content[:100] + "..." if len(doc.content) > 100 else doc.content, meta_str)

            console.print(table)
            console.print(f"\n[green]总共 {len(documents)} 个文档[/green]")
        except Exception as e:
            console.print(f"[red]获取文档列表时出错: {e}[/red]")

    asyncio.run(_list())


if __name__ == "__main__":
    app()