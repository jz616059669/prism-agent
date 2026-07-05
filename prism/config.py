"""
PRISM Agent - 统一配置系统
整合 Hermes/Codex/OpenClaw 配置优势
"""

import os
import yaml
from pathlib import Path
from typing import Any, Optional

from prism.paths import PRISM_HOME, ensure_dirs

try:
    import keyring
except ImportError:
    keyring = None  # type: ignore[assignment]


class ConfigError(Exception):
    """配置校验失败"""
    pass


_SENSITIVE_KEYS = {
    'model.api_key',
    'gateway.feishu.app_secret',
    'gateway.telegram.bot_token',
    'gateway.discord.bot_token',
    'gateway.wechat.corp_secret',
    'gateway.wechat.agent_secret',
}


class Config:
    """统一配置管理"""
    
    def __init__(self):
        self.config_dir = PRISM_HOME
        ensure_dirs()
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
                'default': 'step-3.7-flash',
                'provider': 'stepfun',
                'base_url': 'https://api.stepfun.com/step_plan/v1',
                'api_key': os.getenv('STEPFUN_API_KEY', os.getenv('OPENAI_API_KEY', '')),
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
        """校验必填配置，缺失时提前拦截，避免调用时才炸。"""
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
        api_key = model.get('api_key')
        if not api_key:
            api_key = self._resolve_sensitive('model.api_key', '')
        if not api_key:
            missing.append('model.api_key')

        # 提前拦：已启用平台但缺凭证
        gateway = self._config.get('gateway', {}) or {}
        platforms = gateway.get('platforms') or []
        for platform in platforms:
            if platform == 'feishu':
                if not gateway.get('feishu', {}).get('app_id'):
                    missing.append('gateway.feishu.app_id')
                if not gateway.get('feishu', {}).get('app_secret'):
                    missing.append('gateway.feishu.app_secret')
            elif platform == 'telegram':
                if not gateway.get('telegram', {}).get('token'):
                    missing.append('gateway.telegram.token')
            elif platform == 'discord':
                if not gateway.get('discord', {}).get('bot_token'):
                    missing.append('gateway.discord.bot_token')
            elif platform == 'wechat':
                if not gateway.get('wechat', {}).get('secret'):
                    missing.append('gateway.wechat.secret')
                if not gateway.get('wechat', {}).get('token'):
                    missing.append('gateway.wechat.token')

        if missing:
            raise ConfigError(
                '配置缺失，请先设置：' + ', '.join(missing) +
                '。可用命令：prism config set <key> <value>，或编辑 ' + str(getattr(self, 'config_file', 'config.yaml'))
            )

    def _resolve_sensitive(self, key: str, value: str) -> str:
        """敏感字段优先回退 keyring，其次环境变量，最后保持原值。"""
        if not value and keyring is not None:
            try:
                stored = keyring.get_password("prism", key)
                if stored:
                    return stored
            except Exception:
                pass
        env_name = key.upper().replace('.', '_')
        return value or os.getenv(env_name, '')
    
    def _redact_value(self, value: Any) -> Any:
        """对敏感值做脱敏显示"""
        if isinstance(value, str) and len(value) > 6:
            return f"{value[:3]}***{value[-2:]}"
        return "***"
    
    def _redact_config(self, data: dict) -> dict:
        """递归脱敏配置中的敏感字段"""
        result = {}
        for k, v in data.items():
            full_key = k
            if isinstance(v, dict):
                result[k] = self._redact_config(v)
            elif full_key.lower().endswith('api_key') or full_key.lower().endswith('secret') or full_key.lower().endswith('token'):
                result[k] = self._redact_value(str(v))
            else:
                result[k] = v
        return result
    
    def get(self, key: str, default=None):
        """获取配置项，支持点号分隔的路径"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        if value is None:
            return default
        if key.lower().replace('.', '_') in {
            'model_api_key',
            'gateway_feishu_app_secret',
            'gateway_telegram_bot_token',
            'gateway_discord_bot_token',
            'gateway_wechat_corp_secret',
            'gateway_wechat_agent_secret',
        }:
            return self._resolve_sensitive(key, value)
        return value
    
    def set(self, key: str, value) -> None:
        """设置配置项，支持点号分隔的路径；敏感字段写入 keyring"""
        resolved = value
        if key in _SENSITIVE_KEYS and keyring is not None:
            try:
                keyring.set_password("prism", key, str(value))
                resolved = value
            except Exception:
                resolved = value
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = resolved
        self._save()
    
    def show(self, redact: bool = True) -> dict:
        """返回完整配置，可脱敏"""
        if redact:
            return self._redact_config(self._config)
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
                'path': str(PRISM_HOME / 'sessions'),
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
