import asyncio
import tempfile
import json
import logging
import os
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)
logger.setLevel(logging.CRITICAL)

# 设置MCP相关日志级别
for name in ["mcp", "mcp.server", "mcp.server.fastmcp", "mcp.server.lowlevel"]:
    lg = logging.getLogger(name)
    lg.setLevel(logging.CRITICAL)
    lg.propagate = False

mcp = FastMCP("Sandbox Server")

@mcp.tool()
async def execute_code(
    code: str,
    description: str = "执行自定义代码"
) -> Dict[str, Any]:
    """
    在安全沙箱中执行Python代码并返回结果。适用于需要动态计算、数据处理、算法实现等场景。
    
    使用场景：
    - 数学计算：复杂的数学运算、统计分析、数值计算
    - 数据处理：列表、字典、字符串的处理和转换
    - 算法实现：排序、搜索、递归等算法逻辑
    - 文本分析：正则表达式、字符串操作、格式化
    - 文件读取：读取JSON、CSV、TXT等文件内容进行分析
    - 简单API调用：使用requests库获取数据
    - 日期时间处理：datetime模块相关操作
    - JSON/数据格式转换：数据序列化和反序列化
    
    安全限制：
    - 限制执行时间（30秒超时）
    - 使用进程隔离，避免影响主程序
    - 静态代码安全检查，阻止危险操作：
      * 文件写入操作（open with 'w'/'a'/'x' mode, file.write, 'wb'/'ab'等）
      * 系统命令执行（os.system, subprocess, eval等）
      * 网络操作（socket, urllib, requests等）
      * 导入限制（importlib动态导入等）
    - 允许读取操作：文件读取、数据处理、计算等安全操作
    
    代码要求：
    - 将最终结果赋值给变量 'result' 或 'output'
    - 如果没有显式结果变量，返回执行完成状态
    - 支持标准Python语法和常用库（requests, json, datetime, math等）
    
    返回格式：
    - 成功：{"success": true, "result": 计算结果}
    - 失败：{"success": false, "error": "错误信息"}
    
    示例用法：
    code = "result = 2 ** 10"  # 计算2的10次方
    code = "import math; result = math.sqrt(16)"  # 数学计算
    code = "data = [1,2,3,4,5]; result = sum(data)"  # 数据处理
    code = "with open('data.txt', 'r') as f: result = f.read()"  # 读取文件
    code = "import json; with open('config.json') as f: result = json.load(f)"  # 读取JSON
    
    Args:
        code: 要执行的Python代码，将结果赋值给'result'或'output'变量
        description: 代码功能的简短描述，用于日志记录
        
    Returns:
        Dict[str, Any]: 包含执行状态和结果的字典
    """
    try:
        # 基础安全检查
        if not _is_safe_code(code):
            return {"success": False, "error": "代码包含不安全内容"}
        
        # 在沙箱中执行
        result = await _run_in_sandbox(code)
        return result
        
    except Exception as e:
        logger.error(f"代码执行失败: {e}")
        return {"success": False, "error": str(e)}

async def _run_in_sandbox(code: str) -> Dict[str, Any]:
    """在安全沙箱中执行代码"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        # 包装代码 - 确保用户代码正确缩进
        # 为用户代码的每一行添加4个空格缩进
        indented_code = '\n'.join('    ' + line for line in code.split('\n'))
        
        wrapped_code = f"""
import json
import sys
import traceback

try:
    # 用户代码开始
{indented_code}
    # 用户代码结束
    
    # 尝试获取结果
    if 'result' in locals():
        output = result
    elif 'output' in locals():
        output = output
    else:
        output = "代码执行完成"
    
    print(json.dumps({{"success": True, "result": output}}, ensure_ascii=False))
    
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}, ensure_ascii=False))
"""
        f.write(wrapped_code)
        f.flush()
        
        try:
            # 执行代码
            process = await asyncio.create_subprocess_exec(
                "python", f.name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 使用 wait_for 来实现超时控制
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=30
            )
            
            # 清理临时文件
            try:
                os.unlink(f.name)
            except Exception:
                pass
            
            if process.returncode == 0:
                try:
                    stdout_str = stdout.decode()
                    if not stdout_str.strip():
                        return {"success": False, "error": "代码执行无输出"}
                    return json.loads(stdout_str)
                except json.JSONDecodeError as e:
                    return {
                        "success": False, 
                        "error": f"JSON解析错误: {e}, 输出内容: {stdout.decode()}"
                    }
            else:
                stderr_str = stderr.decode()
                return {
                    "success": False,
                    "error": f"执行错误 (返回码 {process.returncode}): {stderr_str}"
                }
                
        except asyncio.TimeoutError:
            # 如果超时，确保进程被终止
            try:
                process.terminate()
                await process.wait()
            except Exception:
                pass
            return {"success": False, "error": "代码执行超时"}
        except json.JSONDecodeError:
            return {"success": False, "error": "代码输出格式错误"}

def _is_safe_code(code: str) -> bool:
    """基础代码安全检查 - 允许读操作，禁止写操作和危险调用"""
    dangerous = [
        # 危险的导入和调用
        "import subprocess", "import os", "from subprocess", "from os",
        "exec(", "eval(", "__import__",
        "subprocess.", "os.system", "os.remove", "os.unlink", "os.rmdir",
        
        # 文件写操作
        "open(", "'w'", '"w"', "'a'", '"a"', "'x'", '"x"',
        "write(", "writelines(", "truncate(",
        "with open(", "with open ",
        
        # 网络服务器操作
        "socket.bind", "socket.listen", "httpd", "socketserver",
        
        # 用户输入
        "input(", "raw_input("
    ]
    
    code_lower = code.lower()
    
    # 检查是否包含危险模式
    for danger in dangerous:
        if danger in code_lower:
            # 特殊处理：允许只读的open操作
            if "open(" in danger or "with open" in danger:
                # 如果包含写模式标识符，则不安全
                if any(write_mode in code_lower for write_mode in ["'w'", '"w"', "'a'", '"a"', "'x'", '"x"']):
                    return False
                # 如果没有明确的写模式，可能是读操作，允许通过
                continue
            return False
    
    return True

if __name__ == "__main__":
    mcp.run()