"""
PRISM Agent - Skins / Themes
配置驱动的 CLI 主题切换：banner 颜色、spinner、标签等。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from prism.paths import PRISM_HOME

THEMES_DIR = PRISM_HOME / "themes"
DEFAULT_THEME = "default"


@dataclass
class Theme:
    name: str
    banner_color: str = "cyan"
    spinner: str = "dots"
    response_label: str = "PRISM"
    tool_prefix: str = "[tool]"
    border_style: str = "cyan"


_THEME_PRESETS: Dict[str, Theme] = {
    "default": Theme(name="default", banner_color="cyan", spinner="dots", response_label="PRISM", tool_prefix="[tool]", border_style="cyan"),
    "matrix": Theme(name="matrix", banner_color="green", spinner="line", response_label="PRISM", tool_prefix="[matrix]", border_style="green"),
    "warm": Theme(name="warm", banner_color="yellow", spinner="dots", response_label="PRISM", tool_prefix="[tool]", border_style="yellow"),
    "minimal": Theme(name="minimal", banner_color="white", spinner="dots", response_label="", tool_prefix="", border_style="white"),
}


class ThemeManager:
    def __init__(self, theme_dir: Optional[Path] = None) -> None:
        self.theme_dir = theme_dir or THEMES_DIR
        self.theme_dir.mkdir(parents=True, exist_ok=True)
        self._theme_file = self.theme_dir / "current.json"
        self._current: Optional[Theme] = None

    def get_current(self) -> Theme:
        if self._current is not None:
            return self._current
        name = self._load_current_name()
        preset = _THEME_PRESETS.get(name)
        if preset:
            self._current = preset
            return preset
        self._current = _THEME_PRESETS[DEFAULT_THEME]
        return self._current

    def set_current(self, name: str) -> bool:
        if name not in _THEME_PRESETS:
            return False
        payload = json.dumps({"theme": name}, ensure_ascii=False)
        try:
            self._theme_file.write_text(payload, encoding="utf-8")
            self._current = _THEME_PRESETS[name]
            return True
        except OSError:
            try:
                import tempfile
                tmp = Path(tempfile.gettempdir()) / f"prism-theme-{name}.json"
                tmp.write_text(payload, encoding="utf-8")
            except OSError:
                pass
            self._current = _THEME_PRESETS[name]
            return True

    def list_themes(self) -> list:
        builtins = list(_THEME_PRESETS.keys())
        try:
            for p in self.theme_dir.glob("*.json"):
                if p.name == "current.json":
                    continue
                name = p.stem
                if name not in builtins:
                    builtins.append(name)
        except OSError:
            pass
        return builtins

    def _load_current_name(self) -> str:
        if not self._theme_file.exists():
            return DEFAULT_THEME
        try:
            data = json.loads(self._theme_file.read_text(encoding="utf-8"))
            return data.get("theme", DEFAULT_THEME)
        except Exception:
            return DEFAULT_THEME


theme_manager = ThemeManager()


__all__ = ["Theme", "ThemeManager", "theme_manager"]
