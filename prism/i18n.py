"""
PRISM Agent - 多语言支持 i18n
中英切换
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_I18N_DIR = Path.home() / ".prism" / "i18n"
_I18N_DIR.mkdir(parents=True, exist_ok=True)

_DEFAULT_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "zh": {
        "started": "已启动",
        "stopped": "已停止",
        "success": "成功",
        "failed": "失败",
        "settings": "设置",
        "skills": "技能",
        "chat": "对话",
        "help": "帮助",
    },
    "en": {
        "started": "Started",
        "stopped": "Stopped",
        "success": "Success",
        "failed": "Failed",
        "settings": "Settings",
        "skills": "Skills",
        "chat": "Chat",
        "help": "Help",
    },
}


@dataclass
class TranslationBundle:
    language: str = "zh"
    translations: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language": self.language,
            "translations": dict(self.translations),
        }


class I18n:
    def __init__(self) -> None:
        self._bundles: Dict[str, TranslationBundle] = {}
        self._current = "zh"
        self._load_defaults()

    def _load_defaults(self) -> None:
        for lang, items in _DEFAULT_TRANSLATIONS.items():
            bundle = TranslationBundle(language=lang, translations=dict(items))
            self._bundles[lang] = bundle

    def set_language(self, language: str) -> None:
        self._current = language

    def t(self, key: str, default: str = "") -> str:
        bundle = self._bundles.get(self._current)
        if bundle and key in bundle.translations:
            return bundle.translations[key]
        for bundle in self._bundles.values():
            if key in bundle.translations:
                return bundle.translations[key]
        return default or key

    def current_language(self) -> str:
        return self._current


i18n = I18n()
