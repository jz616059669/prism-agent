"""PRISM Desktop - 设置与主题逻辑"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import flet as ft

from prism.logging import logger
import traceback

if TYPE_CHECKING:
    from prism_desktop.main import PrismDesktop


def _load_settings(self: PrismDesktop) -> dict:
    self._settings_path = Path.home() / ".prism" / "desktop_settings.json"
    if self._settings_path.exists():
        try:
            return json.loads(self._settings_path.read_text(encoding="utf-8"))
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())
            return {}
    return {}


def _save_settings(self: PrismDesktop) -> None:
    try:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "window_width": int(self.page.window_width) if self.page.window_width else None,
            "window_height": int(self.page.window_height) if self.page.window_height else None,
            "window_top": int(self.page.window_top) if getattr(self.page, "window_top", None) else None,
            "window_left": int(self.page.window_left) if getattr(self.page, "window_left", None) else None,
            "theme_mode": getattr(self.page.theme_mode, "value", ""),
            "theme_seed": getattr(self.page, "theme_seed", None),
            "sidebar_width": getattr(self, "_sidebar_width", 260),
            "provider": self.provider_textfield.value,
            "model": self.model_dropdown.value,
            "base_url": self.base_url_textfield.value,
            "api_key": self.api_key_textfield.value,
            "current_session": getattr(self, "_current_session_name", None),
        }
        self._settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        self._append_terminal(f"settings save failed: {e}")


def _apply_settings(self: PrismDesktop) -> None:
    if hasattr(self, "_validate_config") and not self._validate_config():
        return
    settings = self._settings
    theme_name = settings.get("theme_mode") or "dark"
    theme_mode_map = {
        "light": ft.ThemeMode.LIGHT,
        "dark": ft.ThemeMode.DARK,
        "system": ft.ThemeMode.SYSTEM,
    }
    self.page.theme_mode = theme_mode_map.get(theme_name.lower(), ft.ThemeMode.DARK)
    theme_seed = self._settings.get("theme_seed")
    if isinstance(theme_seed, str) and theme_seed:
        self.page.theme = ft.Theme(color_scheme_seed=theme_seed)
        self.page.dark_theme = ft.Theme(color_scheme_seed=theme_seed)
    try:
        provider = (self.provider_textfield.value or "").strip()
        base_url = (self.base_url_textfield.value or "").strip()
        api_key = (self.api_key_textfield.value or "").strip()
        model = (self.model_dropdown.value or "").strip()
        if provider:
            prism_config.set("model.provider", provider)
        if base_url:
            prism_config.set("model.base_url", base_url)
        if api_key:
            prism_config.set("model.api_key", api_key)
        if model:
            prism_config.set("model.default", model)
    except Exception:
        logger.debug('desktop exception: %s', traceback.format_exc())
        pass
    current_session = settings.get("current_session")
    if current_session:
        try:
            self._load_session(current_session)
        except Exception:
            logger.debug('desktop exception: %s', traceback.format_exc())
            pass