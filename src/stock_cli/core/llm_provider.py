"""
LLM提供商工厂模块，只支持OpenAI SDK格式
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, AsyncGenerator

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion


logger = logging.getLogger(__name__)


class LLMProvider:
    """LLM提供商包装类，兼容旧接口"""

    def __init__(self, client: AsyncOpenAI, model: str):
        self.client = client
        self.model = model
        self.last_usage = {}

    async def generate(
        self,
        messages: list,
        max_tokens: Optional[int] = None,
        temperature: float = 0.1,
        timeout: int = 120,
    ) -> str:
        """生成文本回复"""
        try:
            response: ChatCompletion = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or 1024,
                temperature=temperature,
                timeout=timeout,
            )

            # 记录使用情况
            if hasattr(response, "usage") and response.usage:
                self.last_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

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
    ) -> AsyncGenerator[str, None]:
        """流式生成文本回复"""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens or 1024,
                temperature=temperature,
                timeout=timeout,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error("Failed to generate stream response: %s", str(e))
            raise


class LLMProviderFactory:
    """LLM提供商工厂类，支持OpenAI格式的API"""

    @staticmethod
    def create_provider(provider_name: str, config: Dict[str, Any]) -> LLMProvider:
        """根据配置创建LLMProvider实例"""
        # 支持的提供商列表
        supported_providers = ["openai", "deepseek"]
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
