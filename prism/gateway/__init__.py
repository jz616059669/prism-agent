"""
PRISM Agent - 统一 Gateway
整合 Hermes 的多平台支持 + OpenClaw 的消息处理
"""
from __future__ import annotations

import importlib
from typing import Callable, Dict, Optional, List

from prism.gateway.base import Message, PlatformAdapter
from prism.logging import logger
import traceback


__all__ = ['Gateway', 'gateway', 'Message', 'PlatformAdapter']


_ADAPTER_MODULES = {
    'feishu': 'prism.gateway.feishu',
    'telegram': 'prism.gateway.telegram',
    'wechat': 'prism.gateway.wechat',
}


class Gateway:
    """
    统一 Gateway
    整合 Hermes 的多平台支持 + OpenClaw 的消息处理
    """

    def __init__(self) -> None:
        self.adapters: Dict[str, PlatformAdapter] = {}
        self.running = False
        self._platforms: List[str] = []

    def load_from_config(self, cfg: Optional[dict]) -> None:
        platforms = ((cfg or {}).get('gateway') or {}).get('platforms') or []
        for platform in platforms:
            self.register_platform(platform)

    def register_platform(self, platform: str) -> bool:
        if platform in self.adapters:
            return True
        try:
            mod = importlib.import_module(_ADAPTER_MODULES.get(platform, f'prism.gateway.{platform}'))
            adapter = mod.build_from_config()
            if adapter is None:
                return False
            self.adapters[platform] = adapter
            self._platforms = list(self.adapters.keys())
            logger.info('registered gateway platform=%s', platform)
            return True
        except Exception as exc:
            logger.debug('register platform failed: %s', traceback.format_exc())
            return False

    def register(self, name: str, adapter: PlatformAdapter):
        self.adapters[name] = adapter
        self._platforms = list(self.adapters.keys())

    def start(self, handler: Callable[[Message], None]):
        self.running = True
        for name, adapter in self.adapters.items():
            try:
                start_fn = getattr(adapter, 'start', None) or getattr(adapter, 'start_polling', None)
                if start_fn is None:
                    raise AttributeError(f"'{type(adapter).__name__}' object has no 'start' or 'start_polling'")
                start_fn(handler)
                logger.info('gateway platform started: %s', name)
            except Exception as exc:
                logger.warning('gateway platform start failed: %s | %s', name, exc)
                logger.debug(traceback.format_exc())

    def stop(self):
        self.running = False
        for name, adapter in self.adapters.items():
            try:
                stop_fn = getattr(adapter, 'stop', None)
                if stop_fn is not None:
                    stop_fn()
                logger.info('gateway platform stopped: %s', name)
            except Exception as exc:
                logger.warning('gateway platform stop failed: %s | %s', name, exc)

    def send(self, platform: str, chat_id: str, text: str) -> bool:
        adapter = self.adapters.get(platform)
        if not adapter:
            return False
        try:
            return bool(adapter.send(chat_id, text))
        except Exception as exc:
            logger.debug('gateway send failed: %s', exc)
            return False

    def get_adapter(self, name: str) -> Optional[PlatformAdapter]:
        return self.adapters.get(name)

    def list_platforms(self) -> List[str]:
        registered = list(self.adapters.keys())
        try:
            from prism.config import config as prism_config
            cfg_platforms = prism_config.get("gateway.platforms") or []
            for platform in cfg_platforms:
                if platform and platform not in registered:
                    registered.append(platform)
        except Exception:
            logger.debug("list platforms failed: %s", traceback.format_exc())
        return registered

    def status(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for name, adapter in self.adapters.items():
            try:
                out[name] = {
                    'running': bool(getattr(adapter, 'running', False)),
                    'type': type(adapter).__name__,
                }
            except Exception:
                out[name] = {'running': False}
        return out


gateway = Gateway()
