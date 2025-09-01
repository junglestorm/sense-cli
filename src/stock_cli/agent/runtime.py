"""
Agent运行时模块：管理AgentKernel实例的生命周期
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any

from .kernel import AgentKernel
from ..core.prompt_loader import prompt_builder
from ..core.llm_provider import LLMProviderFactory
from ..core.types import AgentConfig
from ..core.session import SessionManager
from ..core.config_resolver import resolve_settings_path, load_settings

logger = logging.getLogger(__name__)

# 全局AgentKernel实例
_kernel: Optional[AgentKernel] = None
_current_model: Optional[str] = None

# 全局SessionManager实例
_session_manager: Optional[SessionManager] = None


def current_model() -> Optional[str]:
    """获取当前使用的模型名称"""
    return _current_model


def get_session_manager() -> SessionManager:
    """获取全局SessionManager实例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


async def ensure_kernel(session_id: str = "default", role_config: Optional[Dict[str, Any]] = None, role_name: Optional[str] = None) -> AgentKernel:
    """确保获取AgentKernel实例（懒加载 + 单例），支持可选的角色配置注入"""
    global _kernel, _current_model
    if _kernel is not None:
        return _kernel

    try:
        # 加载配置（通过 config_resolver 发现与读取）
        settings_path = resolve_settings_path()
        settings = load_settings(settings_path)

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
        # 创建SessionManager
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id, role_config, role_name)

        # 根据角色配置调整默认参数
        timeout = 300
        max_iterations = 10
        
        if role_config and isinstance(role_config, dict):
            permissions = role_config.get('permissions', {})
            timeout = permissions.get('timeout', 300)
            max_iterations = permissions.get('max_iterations', 10)

        # 创建Agent配置
        agent_config = AgentConfig(
            timeout=timeout,
            max_iterations=max_iterations,
            llm_model=provider_config.get("model"),
            llm_temperature=0.1,
            llm_max_tokens=4096,
            provider_name=provider_name,
            tool_timeout=30,
            max_tool_retries=3,
        )

        # 创建AgentKernel实例，传入 session
        _kernel = AgentKernel(
            llm_provider=llm_provider,
            session=session,
            prompt_builder=prompt_builder,
            config=agent_config,
        )

        logger.info("AgentKernel 初始化成功，使用模型: %s", _current_model)
        
        # 自动注册监控器
        try:
            from ..monitors import register_all_monitors
            await register_all_monitors()
            logger.info("监控器注册完成")
        except Exception as e:
            logger.warning("监控器注册失败: %s", e)
        
        return _kernel
    except Exception as e:
        logger.error("AgentKernel 初始化失败: %s", e)
        raise e

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