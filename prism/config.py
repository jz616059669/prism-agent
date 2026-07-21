"""
PRISM Agent - 统一配置系统
整合 Hermes/Codex/OpenClaw 配置优势
"""

import json
import os
import threading
import time
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
        self._config_mtime = 0.0
        self._watch_stop = threading.Event()
        self._watch_thread: Optional[threading.Thread] = None
        self._on_change: Optional[Any] = None
        self._load()
        self._start_watcher()
    
    def on_change(self, callback: Any) -> None:
        """注册配置变更回调：接收新旧 config dict"""
        self._on_change = callback
    
    def _start_watcher(self) -> None:
        try:
            if self._watch_thread and self._watch_thread.is_alive():
                return
            self._watch_stop.clear()
            self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
            self._watch_thread.start()
        except Exception:
            logger.debug("config watcher start failed", exc_info=True)
    
    def _watch_loop(self) -> None:
        try:
            while not self._watch_stop.is_set():
                try:
                    mtime = self.config_file.stat().st_mtime if self.config_file.exists() else 0.0
                except OSError:
                    mtime = 0.0
                if mtime and mtime != self._config_mtime:
                    old = self._config.copy()
                    self._load()
                    self._config_mtime = mtime
                    if self._on_change:
                        try:
                            self._on_change(old, self._config.copy())
                        except Exception:
                            logger.debug("config on_change callback failed", exc_info=True)
                self._watch_stop.wait(1.0)
        except Exception:
            logger.debug("config watcher loop failed", exc_info=True)
    
    def stop_watcher(self) -> None:
        self._watch_stop.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=2.0)
    
    def _load(self) -> None:
        """加载配置文件"""
        if self.config_file.exists():
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = self._defaults()
            self._save()

        # 合并桌面端快捷配置，避免同一 key 在 config.yaml 和桌面端各存一份
        # 桌面端配置优先级更高，直接覆盖 config.yaml 中的对应值
        self._merge_desktop_settings()

        # Load hooks config
        self._load_hooks()
        # Load workspaces config
        self._load_workspaces()

        # 配置 schema 校验
        try:
            self._validate_schema()
        except ConfigError as exc:
            raise
        except Exception:
            logger.debug("schema validation skipped", exc_info=True)
    
    def _validate_schema(self) -> None:
        """轻量 schema 校验：类型 + 必填 + 枚举"""
        model = self._config.get('model') or {}
        if not isinstance(model, dict):
            raise ConfigError('model 必须是对象')
        if not model.get('default'):
            raise ConfigError('model.default 必填')
        if not model.get('provider'):
            raise ConfigError('model.provider 必填')
        base_url = model.get('base_url')
        if base_url and not isinstance(base_url, str):
            raise ConfigError('model.base_url 必须是字符串')
        api_key = model.get('api_key')
        if not api_key:
            api_key = self._resolve_sensitive('model.api_key', '')
        if not api_key:
            raise ConfigError('model.api_key 必填')

        api_server = self._config.get('api_server') or {}
        if api_server.get('enabled'):
            host = api_server.get('host')
            port = api_server.get('port')
            if host and not isinstance(host, str):
                raise ConfigError('api_server.host 必须是字符串')
            if port is not None and not isinstance(port, int):
                raise ConfigError('api_server.port 必须是整数')

        memory = self._config.get('memory') or {}
        if memory:
            if not isinstance(memory, dict):
                raise ConfigError('memory 必须是对象')
            if 'enabled' in memory and not isinstance(memory['enabled'], bool):
                raise ConfigError('memory.enabled 必须是布尔值')

        gateway = self._config.get('gateway') or {}
        if gateway:
            if not isinstance(gateway, dict):
                raise ConfigError('gateway 必须是对象')
            platforms = gateway.get('platforms') or []
            if not isinstance(platforms, list):
                raise ConfigError('gateway.platforms 必须是数组')
            for platform in platforms:
                if platform == 'feishu':
                    if not gateway.get('feishu', {}).get('app_id'):
                        raise ConfigError('gateway.feishu.app_id 必填')
                    if not gateway.get('feishu', {}).get('app_secret'):
                        raise ConfigError('gateway.feishu.app_secret 必填')

    def _merge_desktop_settings(self) -> None:
        desktop_settings_file = self.config_dir / "desktop_settings.json"
        if not desktop_settings_file.exists():
            return
        try:
            with open(desktop_settings_file, 'r', encoding='utf-8') as f:
                desktop = json.load(f) or {}
            model_section = self._config.setdefault('model', {})
            desktop_model_map = {
                'api_key': 'api_key',
                'provider': 'provider',
                'base_url': 'base_url',
                'default': 'model',
            }
            env_map = {
                'api_key': 'PRISM_API_KEY',
                'provider': 'PRISM_MODEL_PROVIDER',
                'base_url': 'PRISM_BASE_URL',
                'default': 'PRISM_DEFAULT_MODEL',
            }
            for config_key, desktop_key in desktop_model_map.items():
                value = desktop.get(desktop_key)
                if value:
                    if model_section.get(config_key) and model_section[config_key] != value:
                        logger.debug(
                            "desktop settings overriding config: %s = %r -> %r",
                            config_key, model_section[config_key], value,
                        )
                    model_section[config_key] = value
                if not model_section.get(config_key):
                    env_value = os.getenv(env_map[config_key])
                    if env_value:
                        model_section[config_key] = env_value
        except Exception:
            pass
    
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
                'enabled': False,
                'chain': ['stepfun/step-3.7-flash'],
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
            'batch': {
                'max_workers': 4,
                'retry': 1,
            },
            'api_server': {
                'enabled': False,
                'host': '127.0.0.1',
                'port': 8000,
            },
            'moa': {
                'enabled': False,
                'ensemble': [],
                'aggregate': True,
            },
            'review': {
                'aux_model': '',
            },
            'rag': {
                'enabled': False,
                'root': str(Path.home() / '.prism' / 'rag'),
                'chunk_size': 600,
                'overlap': 120,
                'top_k': 3,
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

    def _resolve_sensitive(self, key: str, fallback: str = "") -> str:
        if keyring is not None:
            try:
                stored = keyring.get_password("prism", key)
                if stored:
                    return stored
            except Exception:
                pass
        env_name = key.upper().replace(".", "_")
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                value = None
                break
        if value is not None:
            return str(value)
        return fallback

    def _redact_value(self, value: Any) -> Any:
        """对敏感值做脱敏显示"""
        if isinstance(value, str) and len(value) > 6:
            return f"{value[:3]}***{value[-2:]}"
        return "***"

    def _redact_config(self, data: dict) -> dict:
        """递归脱敏配置中的敏感字段"""
        result = {}
        for k, v in data.items():
            if isinstance(v, dict):
                result[k] = self._redact_config(v)
            elif k.lower().endswith('api_key') or k.lower().endswith('secret') or k.lower().endswith('token'):
                result[k] = self._redact_value(str(v))
            else:
                result[k] = v
        return result
    
    def get(self, key: str, default=None):
        """获取配置项，支持点号分隔的路径；敏感字段优先从 keyring 回填"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        if value is None:
            return default
        if key in _SENSITIVE_KEYS:
            return self._resolve_sensitive(key, default if default is not None else '')
        return value
    
    def set(self, key: str, value) -> None:
        """设置配置项；敏感字段同时写入 keyring，_config 保留明文供桌面端恢复"""
        if key in _SENSITIVE_KEYS and keyring is not None:
            try:
                keyring.set_password("prism", key, str(value))
            except Exception:
                pass
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self._save()

    def revert(self, key: str) -> None:
        """回滚配置项到默认值"""
        defaults = self._defaults()
        keys = key.split('.')
        default_value = defaults
        for k in keys:
            if isinstance(default_value, dict):
                default_value = default_value.get(k)
            else:
                default_value = None
                break
        if default_value is not None:
            self.set(key, default_value)
    
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

# 配置单例访问器（延迟初始化，避免 import-time 副作用）
_config_instance = None


def get_config() -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


# 向后兼容别名；推荐新代码用 get_config()
config = get_config()
