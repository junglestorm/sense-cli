"""
Agent运行时模块：管理AgentKernel实例的生命周期
"""

from __future__ import annotations

import logging
from typing import Optional
from pathlib import Path

import yaml

from .kernel import AgentKernel
from ..core.context import ContextManager, MemoryManager
from ..core.prompt_loader import prompt_builder
from ..core.llm_provider import LLMProviderFactory
from ..core.types import AgentConfig

logger = logging.getLogger(__name__)

# 全局AgentKernel实例
_kernel: Optional[AgentKernel] = None
_current_model: Optional[str] = None


def current_model() -> Optional[str]:
    """获取当前使用的模型名称"""
    return _current_model


async def ensure_kernel() -> AgentKernel:
    """确保获取AgentKernel实例（懒加载 + 单例）"""
    global _kernel, _current_model
    if _kernel is not None:
        return _kernel

    try:
        # 加载配置
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        settings_path = project_root / "config" / "settings.yaml"

        if not settings_path.exists():
            raise RuntimeError(f"配置文件未找到: {settings_path}")

        with open(settings_path, "r", encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        # 获取LLM配置
        llm_settings = settings.get("llm", {})
        provider_name = llm_settings.get("provider")
        
        if not provider_name:
            # 如果未指定 provider，则遍历所有 provider，选第一个有配置的
            valid_providers = [
                "openai",
                "deepseek",
                "ollama",
                "gemini",
                "anthropic",
                "azure",
                "custom",
                "aihubmix",
            ]
            for provider in valid_providers:
                if provider in llm_settings:
                    provider_name = provider
                    break

        provider_config = llm_settings.get(provider_name, {}) if provider_name else {}
        
        if not provider_config:
            raise RuntimeError("未找到LLM配置，请检查 config/settings.yaml")

        # 创建LLM提供者
        try:
            llm_provider = LLMProviderFactory.create_provider(
                provider_name, provider_config
            )
            _current_model = provider_config.get("model")
        except Exception as e:
            raise RuntimeError(f"创建LLM提供者失败: {e}")

        # 初始化核心组件
        # 先创建MemoryManager
        memory_config = settings.get("database", {})
        memory_manager = MemoryManager(memory_config)
        # 再创建ContextManager
        context_manager = ContextManager(memory_manager)

        # 创建Agent配置
        agent_config = AgentConfig(
            max_iterations=20,
            timeout_seconds=300,
            default_model=provider_config.get("model"),
            fallback_model=provider_config.get(
                "fallback_model", provider_config.get("model")
            ),
        )

        # 创建AgentKernel实例
        _kernel = AgentKernel(
            llm_provider=llm_provider,
            context_manager=context_manager,
            prompt_builder=prompt_builder,
            config=agent_config,
        )

        logger.info("AgentKernel 初始化成功，使用模型: %s", _current_model)
        return _kernel
    except Exception as e:
        logger.error("AgentKernel 初始化失败: %s", str(e))
        raise


async def cleanup_kernel():
    """清理AgentKernel实例"""
    global _kernel
    if _kernel is not None:
        # 可以在这里添加任何需要的清理逻辑
        _kernel = None


def get_kernel() -> AgentKernel:
    """获取当前的AgentKernel实例"""
    global _kernel
    if _kernel is None:
        raise RuntimeError("AgentKernel 尚未初始化")
    return _kernel
