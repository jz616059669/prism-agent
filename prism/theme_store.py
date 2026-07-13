"""
PRISM Agent - 主题/皮肤系统
桌面端亮色/暗色/自定义主题
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_THEME_DIR = Path.home() / ".prism" / "themes"
_THEME_DIR.mkdir(parents=True, exist_ok=True)

_LIGHT = {
    "background": "#ffffff",
    "surface": "#f5f5f5",
    "primary": "#1976d2",
    "text": "#212121",
    "bubble_user": "#e3f2fd",
    "bubble_agent": "#f5f5f5",
}

_DARK = {
    "background": "#121212",
    "surface": "#1e1e1e",
    "primary": "#90caf9",
    "text": "#e0e0e0",
    "bubble_user": "#1e3a5f",
    "bubble_agent": "#2c2c2c",
}


@dataclass
class Theme:
    name: str
    colors: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "colors": dict(self.colors),
        }


class ThemeStore:
    def __init__(self) -> None:
        self._themes: Dict[str, Theme] = {}
        self._current = "light"
        self._load_defaults()

    def _load_defaults(self) -> None:
        self._themes["light"] = Theme(name="light", colors=dict(_LIGHT))
        self._themes["dark"] = Theme(name="dark", colors=dict(_DARK))

    def set_current(self, name: str) -> bool:
        if name not in self._themes:
            return False
        self._current = name
        return True

    def current(self) -> Theme:
        return self._themes.get(self._current, self._themes["light"])

    def add_theme(self, theme: Theme) -> Theme:
        self._themes[theme.name] = theme
        try:
            (_THEME_DIR / f"{theme.name}.json").write_text(
                json.dumps(theme.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return theme

    def list_themes(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._themes.values()]


theme_store = ThemeStore()
