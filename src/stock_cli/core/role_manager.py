"""
角色配置管理器：负责加载、验证和管理角色配置文件
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RoleConfig:
    """角色配置数据类"""
    name: str
    description: str
    system_prompt: str
    allowed_mcp_servers: List[str]
    permissions: Dict[str, Any]

class RoleManager:
    """角色管理器"""
    
    def __init__(self, roles_dir: Optional[str] = None):
        self.roles_dir = roles_dir or self._get_default_roles_dir()
        self._roles: Dict[str, RoleConfig] = {}
        self._load_all_roles()
    
    def _get_default_roles_dir(self) -> str:
        """获取默认角色配置目录"""
        # 使用绝对路径计算，确保正确找到项目根目录
        current_file = os.path.abspath(__file__)
        # 需要向上跳4级目录才能到达项目根目录
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        return os.path.join(project_root, "config", "roles")
    
    def _load_all_roles(self) -> None:
        """加载所有角色配置文件"""
        roles_dir = Path(self.roles_dir)
        if not roles_dir.exists():
            logger.warning(f"角色配置目录不存在: {self.roles_dir}")
            return
        
        for yaml_file in roles_dir.glob("*.yaml"):
            try:
                role_config = self._load_role_config(yaml_file)
                if role_config:
                    self._roles[role_config.name] = role_config
                    logger.info(f"成功加载角色: {role_config.name}")
            except Exception as e:
                logger.error(f"加载角色配置文件失败 {yaml_file}: {e}")
    
    def _load_role_config(self, file_path: Path) -> Optional[RoleConfig]:
        """加载单个角色配置文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        if not config_data:
            return None
        # 验证必需字段
        required_fields = ['name', 'system_prompt', 'allowed_mcp_servers']
        for field in required_fields:
            if field not in config_data:
                raise ValueError(f"角色配置文件缺少必需字段: {field}")
        return RoleConfig(
            name=config_data['name'],
            description=config_data.get('description', ''),
            system_prompt=config_data['system_prompt'],
            allowed_mcp_servers=config_data['allowed_mcp_servers'],
            permissions=config_data.get('permissions', {})
        )
    
    def get_role(self, role_name: str) -> Optional[RoleConfig]:
        """获取指定角色配置"""
        return self._roles.get(role_name)
    
    def role_config_to_dict(self, role_config: RoleConfig) -> Dict[str, Any]:
        """将RoleConfig对象转换为字典格式"""
        return {
            "name": role_config.name,
            "system_prompt": role_config.system_prompt,
            "allowed_mcp_servers": role_config.allowed_mcp_servers,
            "permissions": role_config.permissions
        }
    
    def list_roles(self) -> List[str]:
        """列出所有可用角色名称"""
        return list(self._roles.keys())
    
    def validate_role_config(self, role_config: RoleConfig, 
                           available_mcp_servers: List[str]) -> List[str]:
        """验证角色配置的有效性"""
        errors = []
        # 验证MCP服务器
        for server in role_config.allowed_mcp_servers:
            if server not in available_mcp_servers:
                errors.append(f"MCP服务器 '{server}' 不存在")
        return errors

# 全局角色管理器实例
_role_manager_instance: Optional[RoleManager] = None

def get_role_manager() -> RoleManager:
    """获取全局角色管理器实例（单例模式）"""
    global _role_manager_instance
    if _role_manager_instance is None:
        _role_manager_instance = RoleManager()
    return _role_manager_instance

def reload_roles() -> None:
    """重新加载所有角色配置"""
    global _role_manager_instance
    _role_manager_instance = RoleManager()