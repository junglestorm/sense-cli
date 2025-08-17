"""
MCP Server Manager - 重构优化版

主要改进：
1. 添加工具缓存机制，提升性能
2. 线程安全的单例实现
3. 更好的错误处理和日志记录
4. 代码结构优化，提升可维护性
5. 连接池管理，优化资源使用
"""

import os
import json
import shutil
import logging
import asyncio
import threading
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, ClassVar
from contextlib import AsyncExitStack
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

from ..logs.logger import get_logger

logger = get_logger(__name__)


class ServerType(Enum):
    """服务器类型枚举"""

    STDIO = "stdio"


@dataclass
class ServerConfig:
    """服务器配置数据类"""

    name: str
    type: ServerType
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


@dataclass
class CachedTool:
    """缓存的工具信息"""

    name: str
    description: str
    input_schema: Dict[str, Any]
    server_name: str

    def to_tool(self) -> "Tool":
        """转换为Tool对象"""
        return Tool(self.name, self.description, self.input_schema)


class Tool:
    """工具类 - 保持原有接口不变"""

    def __init__(
        self, name: str, description: str, input_schema: Dict[str, Any]
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema

    def format_for_llm(self) -> str:
        """格式化工具信息供LLM使用"""
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                arg_desc = (
                    f"- {param_name}: {param_info.get('description', 'No description')}"
                )
                if param_name in self.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

        args_text = "\n".join(args_desc) if args_desc else "No arguments"
        return f"Tool: {self.name}\nDescription: {self.description}\nArguments:\n{args_text}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


class MCPServerManager:
    """
    MCP服务器管理器 - 重构优化版

    主要优化：
    - 线程安全的单例模式
    - 工具缓存机制
    - 更好的错误处理
    - 连接重试机制
    - 清晰的代码结构
    """

    _instance: ClassVar[Optional["MCPServerManager"]] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()
    _initialized: ClassVar[bool] = False

    def __init__(self, mcp_config_path: Optional[str] = None):
        """初始化管理器"""
        self.config_path = self._get_config_path(mcp_config_path)
        self.servers_config: List[ServerConfig] = []
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack: Optional[AsyncExitStack] = None

        # 工具缓存
        self._tool_cache: Dict[str, CachedTool] = {}
        self._cache_timestamp: Optional[float] = None
        self._cache_ttl: float = 300.0  # 5分钟缓存

    @staticmethod
    def _get_config_path(custom_path: Optional[str]) -> str:
        """获取配置文件路径"""
        if custom_path:
            return custom_path

        current_file = os.path.abspath(__file__)
        # 从 src/stock_cli/tools/mcp_server_manager.py 回退到项目根目录需要4层
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
        )
        return os.path.join(project_root, "config", "mcp_config.json")

    @classmethod
    async def get_instance(cls) -> "MCPServerManager":
        """线程安全的单例获取"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # 双重检查
                    cls._instance = MCPServerManager()

        if not cls._initialized:
            with cls._lock:
                if not cls._initialized:  # 双重检查
                    await cls._instance.initialize()
                    cls._initialized = True

        return cls._instance

    def _load_config(self) -> None:
        """加载MCP配置"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"MCP配置文件未找到: {self.config_path}")

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)

            self.servers_config = []
            for server_data in config_data.get("servers", []):
                server_type = ServerType(server_data.get("type", "stdio"))
                config = ServerConfig(
                    name=server_data["name"],
                    type=server_type,
                    command=server_data.get("command"),
                    args=server_data.get("args", []),
                    env=server_data.get("env", {}),
                    url=server_data.get("url"),
                    headers=server_data.get("headers", {}),
                )
                self.servers_config.append(config)

        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"配置文件格式错误: {e}")

    async def initialize(self) -> None:
        """初始化所有MCP会话"""
        self._load_config()
        self.exit_stack = AsyncExitStack()
        self.sessions.clear()

        initialization_tasks = []
        for config in self.servers_config:
            task = self._initialize_server(config)
            initialization_tasks.append(task)

        # 并行初始化所有服务器
        results = await asyncio.gather(*initialization_tasks, return_exceptions=True)

        successful_count = sum(
            1 for result in results if not isinstance(result, Exception)
        )
        logger.info(
            f"成功初始化 {successful_count}/{len(self.servers_config)} 个服务器"
        )

    async def _initialize_server(self, config: ServerConfig) -> None:
        """初始化单个服务器（仅支持 STDIO）"""
        try:
            session = await self._create_stdio_session(config)
            await session.initialize()
            self.sessions[config.name] = session
            logger.info(f"服务器 {config.name} 初始化成功")
        except Exception as e:
            logger.error(f"初始化服务器 {config.name} 失败: {e}")
            raise


    async def _create_stdio_session(self, config: ServerConfig) -> ClientSession:
        """创建STDIO会话"""
        command = self._resolve_command(config.command)
        if not command:
            raise ValueError(f"无效的命令: {config.command}")

        env = {**os.environ, **(config.env or {})} if config.env else None
        server_params = StdioServerParameters(
            command=command, args=config.args or [], env=env
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        read, write = stdio_transport
        return await self.exit_stack.enter_async_context(ClientSession(read, write))

    @staticmethod
    def _resolve_command(command: Optional[str]) -> Optional[str]:
        """解析命令路径"""
        if not command:
            return None

        if command == "npx":
            return shutil.which("npx")

        return command

    def _is_cache_valid(self) -> bool:
        """检查缓存是否有效"""
        if not self._cache_timestamp:
            return False

        import time

        return (time.time() - self._cache_timestamp) < self._cache_ttl

    async def _refresh_tool_cache(self) -> None:
        """刷新工具缓存"""
        self._tool_cache.clear()

        for server_name, session in self.sessions.items():
            try:
                tools_response = await session.list_tools()
                self._parse_tools_response(tools_response, server_name)
            except Exception as e:
                logger.error(f"从服务器 {server_name} 获取工具失败: {e}")

        import time

        self._cache_timestamp = time.time()

    def _parse_tools_response(self, tools_response: Any, server_name: str) -> None:
        """解析工具响应：仅支持事件流 [("tools", [tool,...]), ...]"""
        def _process_tool(tool_obj: Any) -> None:
            try:
                schema_obj = getattr(tool_obj, "inputSchema", None) or getattr(tool_obj, "input_schema", None) or {}
                input_schema = self._extract_input_schema(schema_obj)
                cached_tool = CachedTool(
                    name=getattr(tool_obj, "name", "unknown"),
                    description=getattr(tool_obj, "description", ""),
                    input_schema=input_schema,
                    server_name=server_name,
                )
                self._tool_cache[cached_tool.name] = cached_tool
            except Exception as e:
                logger.error(f"解析工具 {getattr(tool_obj, 'name', 'unknown')} 失败: {e}")
    
        try:
            for item in tools_response:
                if isinstance(item, tuple) and len(item) >= 2 and item[0] == "tools":
                    for tool in item[1]:
                        _process_tool(tool)
        except TypeError:
            logger.warning('list_tools 返回值不可迭代，期望事件流形式：[("tools", [...]), ...]')

    @staticmethod
    def _extract_input_schema(input_schema: Any) -> Dict[str, Any]:
        """提取输入模式"""
        if hasattr(input_schema, "_asdict"):
            return input_schema._asdict()
        elif isinstance(input_schema, dict):
            return input_schema
        else:
            return dict(input_schema)

    async def list_tools(self) -> List[Tool]:
        """列出所有可用工具 - 使用缓存优化"""
        if not self.sessions:
            raise RuntimeError("没有初始化MCP会话")

        if not self._is_cache_valid():
            await self._refresh_tool_cache()

        return [cached_tool.to_tool() for cached_tool in self._tool_cache.values()]

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        server_name: Optional[str] = None,
        retries: int = 2,
        delay: float = 1.0,
    ) -> Any:
        """调用指定工具 - 优化查找逻辑"""
        if not self.sessions:
            raise RuntimeError("没有初始化MCP会话")

        # 从缓存中查找工具
        if not self._is_cache_valid():
            await self._refresh_tool_cache()

        if tool_name not in self._tool_cache:
            raise RuntimeError(f"工具 {tool_name} 不存在")

        cached_tool = self._tool_cache[tool_name]
        target_server = server_name or cached_tool.server_name

        if target_server not in self.sessions:
            raise RuntimeError(f"服务器 {target_server} 不可用")

        return await self._execute_tool_with_retry(
            target_server, tool_name, arguments, retries, delay
        )

    async def _execute_tool_with_retry(
        self,
        server_name: str,
        tool_name: str,
        arguments: Dict[str, Any],
        retries: int,
        delay: float,
    ) -> Any:
        """带重试的工具执行"""
        last_error = None

        for attempt in range(retries):
            try:
                session = self.sessions[server_name]
                result = await session.call_tool(tool_name, arguments)
                logger.debug(f"工具 {tool_name} 执行成功 (尝试 {attempt + 1})")
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"工具 {tool_name} 执行失败 (尝试 {attempt + 1}): {e}")

                if attempt < retries - 1:
                    await asyncio.sleep(delay)

        raise last_error or RuntimeError("工具执行失败")

    # 保持原有接口兼容性
    def load_mcp_config(self) -> None:
        """加载MCP配置 - 兼容接口"""
        self._load_config()

    async def cleanup(self) -> None:
        """清理所有资源"""
        try:
            if self.exit_stack:
                await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"清理资源时出错: {e}")
        finally:
            self.sessions.clear()
            self._tool_cache.clear()
            self._cache_timestamp = None
            type(self)._initialized = False


