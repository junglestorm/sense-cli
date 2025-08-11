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
from .human_loop import create_default_human_loop

logger = logging.getLogger(__name__)

# 全局AgentKernel实例
_kernel: Optional[AgentKernel] = None
_current_model: Optional[str] = None


def current_model() -> Optional[str]:
    """获取当前使用的模型名称"""
    return _current_model


async def ensure_kernel(
    enable_human_loop: bool = False,
    console=None,
    high_risk_tools: list = None,
    require_final_approval: bool = False,
) -> AgentKernel:
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

        # 查找有效的LLM提供商配置
        valid_providers = [
            "openai",
            "deepseek",
            "ollama",
            "gemini",
            "anthropic",
            "azure",
            "custom",
        ]
        provider_name = None
        provider_config = None

        # 优先使用deepseek配置，如果没有则使用第一个有效的配置
        if "deepseek" in llm_settings:
            config = llm_settings["deepseek"]
            # 检查配置是否完整
            if config.get("api_key") and config.get("base_url") and config.get("model"):
                provider_name = "deepseek"
                provider_config = config
        else:
            # 如果没有deepseek配置，则使用第一个有效的配置
            for provider in valid_providers:
                if provider in llm_settings:
                    config = llm_settings[provider]
                    # 检查配置是否完整
                    if (
                        config.get("api_key")
                        and config.get("base_url")
                        and config.get("model")
                    ):
                        provider_name = provider
                        provider_config = config
                        break
                    elif (
                        provider == "ollama"
                        and config.get("base_url")
                        and config.get("model")
                    ):
                        # 特殊处理ollama，api_key可以是"ollama"
                        provider_name = provider
                        provider_config = config
                        break

        if not provider_name or not provider_config:
            raise RuntimeError("未找到有效的LLM配置，请检查 config/settings.yaml")

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

        # 加载提示词
        # 由于PromptLoader没有load_all_prompts方法，我们跳过这一步
        # await prompt_loader.load_all_prompts()

        # 创建Agent配置
        agent_config = AgentConfig(
            max_iterations=20,
            timeout_seconds=300,
            default_model=provider_config.get("model"),
            fallback_model=provider_config.get(
                "fallback_model", provider_config.get("model")
            ),
        )

        # 创建Human-in-the-Loop管理器（如果启用）
        human_loop_manager = None
        if enable_human_loop:
            human_loop_manager = create_default_human_loop(
                console=console,
                high_risk_tools=high_risk_tools,
                require_final_approval=require_final_approval,
            )
            logger.info("Human-in-the-Loop 已启用")

        # 创建AgentKernel实例
        _kernel = AgentKernel(
            llm_provider=llm_provider,
            context_manager=context_manager,
            prompt_builder=prompt_builder,
            config=agent_config,
            human_loop_manager=human_loop_manager,
        )

        logger.info("AgentKernel 初始化成功，使用模型: %s", _current_model)
        return _kernel
    except Exception as e:
        logger.error("AgentKernel 初始化失败: %s", str(e))
        raise
