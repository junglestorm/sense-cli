#!/usr/bin/env python3
"""
配置检查脚本
检查 config/settings.yaml 是否正确配置
"""

import os
import sys
from pathlib import Path

def check_config():
    """检查配置文件"""
    config_path = Path("config/settings.yaml")
    example_path = Path("config/settings.example.yaml")
    
    print("🔧 Stock CLI 配置检查")
    print("=" * 40)
    
    # 检查配置文件是否存在
    if not config_path.exists():
        print("❌ 配置文件不存在")
        print(f"请复制示例配置文件：")
        print(f"   cp {example_path} {config_path}")
        if example_path.exists():
            print("✅ 找到示例配置文件")
        else:
            print("❌ 示例配置文件也不存在")
        return False
    
    print("✅ 配置文件存在")
    
    # 检查配置内容
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 检查基本结构
        if 'llm' not in config:
            print("❌ 缺少 'llm' 配置节")
            return False
        
        print("✅ 配置文件格式正确")
        
        # 检查API密钥
        api_keys_found = False
        for provider, settings in config['llm'].items():
            if isinstance(settings, dict) and 'api_key' in settings:
                api_key = settings['api_key']
                if api_key and not api_key.startswith('your-'):
                    api_keys_found = True
                    print(f"✅ {provider} API密钥已配置")
                else:
                    print(f"⚠️  {provider} API密钥未配置（使用占位符）")
        
        if not api_keys_found:
            print("❌ 没有找到有效的API密钥")
            print("请编辑 config/settings.yaml 并添加真实的API密钥")
            return False
        
        print("\n🎉 配置检查通过！可以开始使用 Stock CLI")
        return True
        
    except Exception as e:
        print(f"❌ 配置文件解析错误: {e}")
        return False

if __name__ == "__main__":
    # 切换到项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    success = check_config()
    sys.exit(0 if success else 1)
