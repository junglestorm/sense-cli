"""配置解析与发现模块

职责单一：
- 发现 settings.yaml 的路径（支持 CLI 覆盖、环境变量、默认路径与示例兜底）
- 加载 YAML 为 dict
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Dict, Any

import yaml


ENV_SETTINGS_PATH = "STOCK_CLI_SETTINGS"


def resolve_settings_path(provided: Optional[str] = None) -> Path:
    """
    发现配置文件路径的优先级：
    1) CLI 显式提供的 --config
    2) 环境变量 STOCK_CLI_SETTINGS
    3) 默认 ./config/settings.yaml
    4) 兜底 ./config/settings.example.yaml（并提示使用者复制为 settings.yaml）
    """
    if provided:
        p = Path(provided).expanduser().resolve()
        if p.exists():
            return p
        raise RuntimeError(f"未找到配置文件: {p}")

    env_path = os.getenv(ENV_SETTINGS_PATH)
    if env_path:
        p = Path(env_path).expanduser().resolve()
        if p.exists():
            return p
        raise RuntimeError(f"环境变量 {ENV_SETTINGS_PATH} 指向的配置不存在: {p}")

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    default = project_root / "config" / "settings.yaml"
    if default.exists():
        return default

    example = project_root / "config" / "settings.example.yaml"
    if example.exists():
        # 允许示例作为兜底，以便开箱即用；但仍建议用户复制为正式文件
        return example

    raise RuntimeError("未找到 settings.yaml 或 settings.example.yaml，请先在 config/ 目录下创建配置。")


def load_settings(path: Path) -> Dict[str, Any]:
    """加载 YAML 配置为 dict，提供清晰错误提示"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError("配置文件必须是 YAML 字典结构")
        return data
    except Exception as e:
        raise RuntimeError(f"加载配置失败 {path}: {e}")


def resolve_triggers_path(provided: Optional[str] = None) -> Path:
    """
    发现触发器配置文件路径的优先级：
    1) CLI 显式提供的 --triggers-config
    2) 默认 ./config/triggers.yaml
    """
    if provided:
        p = Path(provided).expanduser().resolve()
        if p.exists():
            return p
        raise RuntimeError(f"未找到触发器配置文件: {p}")

    project_root = Path(__file__).resolve().parent.parent.parent.parent
    default = project_root / "config" / "triggers.yaml"
    if default.exists():
        return default

    raise RuntimeError("未找到 triggers.yaml，请先在 config/ 目录下创建触发器配置。")


def load_triggers_config(path: Path) -> Dict[str, Any]:
    """加载触发器 YAML 配置为 dict，提供清晰错误提示"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            raise ValueError("触发器配置文件必须是 YAML 字典结构")
        return data
    except Exception as e:
        raise RuntimeError(f"加载触发器配置失败 {path}: {e}")