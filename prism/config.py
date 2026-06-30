"""
PRISM Agent - 统一配置系统
整合 Hermes/Codex/OpenClaw 配置优势
"""

import os
import yaml
from pathlib import Path
from typing import Optional


class ConfigError(Exception):
    """配置校验失败"""
    pass


class Config:
    """统一配置管理"""
    
    def __init__(self):
        self.config_dir = Path.home() / ".prism"
        self.config_file = self.config_dir / "config.yaml"
        self.env_file = self.config_dir / ".env"
        self._config = {}
        self._load()
    
    def _load(self) -> None:
        """加载配置文件"""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._defaults()
            self._save()
        # Load hooks config
        self._load_hooks()
        # Load workspaces config
        self._load_workspaces()
    
    def _save(self) -> None:
        """保存配置文件"""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(self._config, f, allow_unicode=True, default_flow_style=False)
    
    def _defaults(self) -> dict:
        """默认配置"""
        return {
            'model': {
                'default': 'gpt-4o',
                'provider': 'openai',
                'base_url': 'https://api.openai.com/v1',
                'api_key': os.getenv('OPENAI_API_KEY', ''),
                'context_length': 128000,
                'max_tokens': 4096,
            },
            'fallback': {
                'enabled': True,
                'chain': ['openai/gpt-4o', 'anthropic/claude-sonnet-4', 'openai/gpt-4o-mini'],
            },
            'agent': {
                'max_turns': 150,
                'tool_use_enforcement': 'auto',
                'parallel_tools': True,
            },
            'terminal': {
                'timeout': 180,
                'backend': 'local',
            },
            'gateway': {
                'enabled': False,
                'platforms': [],
            },
            'toolsets': [
                'file',
                'terminal',
                'web',
                'browser',
                'code_execution',
            ],
            'skills': {
                'auto_update': True,
                'hub': 'https://hub.prism-agent.com',
            },
            'memory': {
                'enabled': True,
                'provider': 'local',
                'max_tokens': 10000,
            },
            'mcp': {
                'servers': [],
                'auto_discover': True,
            },
        }
    
    def validate(self) -> None:
        """校验必填配置"""
        model = self._config.get('model', {})
        missing = []
        if not model.get('default'):
            missing.append('model.default')
        if not model.get('provider'):
            missing.append('model.provider')
        if not model.get('base_url'):
            missing.append('model.base_url')
        elif not isinstance(model.get('base_url'), str) or not model.get('base_url').startswith('http'):
            raise ConfigError(
                '配置错误：model.base_url 不合法，应以 http/https 开头，当前值：' + str(model.get('base_url'))
            )
        if not model.get('api_key'):
            missing.append('model.api_key')
        if missing:
            raise ConfigError(
                '配置缺失，请先设置：' + ', '.join(missing) +
                '。可用命令：prism config set <key> <value>，或编辑 ' + str(self.config_file)
            )
    
    def get(self, key: str, default=None):
        """获取配置项，支持点号分隔的路径"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def set(self, key: str, value) -> None:
        """设置配置项，支持点号分隔的路径"""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self._save()
    
    def show(self) -> dict:
        """返回完整配置"""
        return self._config
    
    def path(self) -> str:
        """返回配置文件路径"""
        return str(self.config_file)
    
    def env_path(self) -> str:
        """返回.env文件路径"""
        return str(self.env_file)


    def _load_hooks(self) -> None:
        """加载 hooks 配置"""
        hooks_cfg = self._config.get('hooks', [])
        self._config['_hooks'] = hooks_cfg if isinstance(hooks_cfg, list) else []

    def _load_workspaces(self) -> None:
        """加载 workspaces 配置"""
        workspaces_cfg = self._config.get('workspaces', [])
        if not workspaces_cfg:
            # 创建默认工作区
            workspaces_cfg = [{
                'name': 'default',
                'path': str(Path.home() / '.prism' / 'sessions'),
                'description': 'Default workspace',
                'tags': ['main'],
            }]
        self._config['_workspaces'] = workspaces_cfg

    def get_hooks(self) -> list:
        """获取 hooks 配置"""
        return self._config.get('_hooks', [])

    def get_workspaces(self) -> list:
        """获取 workspaces 配置"""
        return self._config.get('_workspaces', [])

    def add_workspace(self, name: str, path: str, description: str = "", tags: list = None) -> None:
        """添加工作区"""
        workspaces = self._config.get('_workspaces', [])
        if any(w.get('name') == name for w in workspaces):
            raise ValueError(f"Workspace '{name}' already exists")
        workspaces.append({
            'name': name,
            'path': path,
            'description': description,
            'tags': tags or [],
        })
        self._config['_workspaces'] = workspaces
        self._config['workspaces'] = workspaces
        self._save()

# 全局配置实例
config = Config()
