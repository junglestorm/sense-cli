"""LLM Provider & Factory (OpenAI 兼容)

注意: from __future__ import annotations 必须位于文件最顶部。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Union, AsyncGenerator, Dict, Any, Optional
import logging


@dataclass
class ChatMessage:
    """结构化对话消息对象。"""
    role: Literal["system", "assistant", "tool", "user"]
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}

# ---------------------------------------------------------------------------
# LLM Provider
# ---------------------------------------------------------------------------

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion


logger = logging.getLogger(__name__)


class LLMProvider:
    """LLM提供商包装类，兼容旧接口"""

    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model

    # ------------------------------------------------------------------
    # 高层消息接口（推荐使用）
    # ------------------------------------------------------------------
    async def send_messages(
        self,
        messages: List[Union[ChatMessage, Dict[str, str]]],
        *,
        stream: bool = False,
        max_tokens: Optional[int] = None,
        temperature: float = 0.1,
        timeout: int = 120,
        provider: str = "openai",
    ) -> Union[str, AsyncGenerator[str, None]]:
        """统一的消息发送入口。

        若 stream=True 返回异步生成器；否则返回完整字符串。
        接受 ChatMessage 或已经是 dict 的消息。
        """
        normalized = [m.to_dict() if isinstance(m, ChatMessage) else m for m in messages]
        if stream:
            return self.generate_stream(
                normalized,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
                provider=provider,
            )
        else:
            return await self.generate(
                normalized,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
                provider=provider,
            )

    async def generate(
        self,
        messages: list,
        max_tokens: Optional[int] = None,
        temperature: float = 0.1,
        timeout: int = 120,
        provider: str = "openai",
    ) -> str:
        """生成文本回复"""
        try:
            # 动态选择参数名
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "timeout": timeout,
            }
            if provider in ["openai", "aihubmix", "deepseek"]:
                params["max_completion_tokens"] = max_tokens or 1024
            else:
                params["max_tokens"] = max_tokens or 1024

            response: ChatCompletion = await self.client.chat.completions.create(**params)

            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("Failed to generate response: %s", str(e))
            raise

    async def generate_stream(
        self,
        messages: list,
        max_tokens: Optional[int] = None,
        temperature: float = 0.1,
        timeout: int = 120,
        provider: str = "openai",
    ) -> AsyncGenerator[str, None]:
        """流式生成文本回复"""
        try:
            params = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "timeout": timeout,
                "stream": True,
            }
            if provider in ["openai", "aihubmix", "deepseek"]:
                params["max_completion_tokens"] = max_tokens or 1024
            else:
                params["max_tokens"] = max_tokens or 1024

            stream = await self.client.chat.completions.create(**params)

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            # 明确区分超时异常
            if "timeout" in str(e).lower() or isinstance(e, TimeoutError):
                logger.error("模型调用超时: %s", str(e))
                raise TimeoutError("模型服务超时，请稍后重试或检查服务商状态。")
            logger.error("Failed to generate stream response: %s", str(e))
            raise


class LLMProviderFactory:
    """LLM提供商工厂类，支持OpenAI格式的API"""

    @staticmethod
    def create_provider(provider_name: str, config: Dict[str, Any]) -> LLMProvider:
        """根据配置创建LLMProvider实例"""
        # 支持的提供商列表
        supported_providers = ["openai", "deepseek", "ollama"]
        if provider_name not in supported_providers:
            raise ValueError(
                f"Unsupported provider: {provider_name}. Supported providers: {supported_providers}"
            )

        client = LLMProviderFactory._create_openai_compatible_provider(config)
        model = config.get("model", "gpt-4o-mini")
        return LLMProvider(client, model)

    @staticmethod
    def _create_openai_compatible_provider(config: Dict[str, Any]) -> AsyncOpenAI:
        """创建OpenAI或兼容接口的LLM客户端实例"""
        try:
            # 从配置中获取参数
            api_key = config.get("api_key")
            base_url = config.get("base_url")
            timeout = config.get("timeout", 120)

            # 验证必要参数
            if not api_key or not base_url:
                raise ValueError("Missing required config: api_key or base_url")

            # 创建并返回AsyncOpenAI实例
            return AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        except Exception as e:
            logger.error("Failed to create OpenAI compatible provider: %s", str(e))
            raise