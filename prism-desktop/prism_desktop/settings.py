"""PRISM Desktop - 设置面板逻辑"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

import flet as ft

from prism.logging import logger
import traceback

if TYPE_CHECKING:
    from prism_desktop.main import PrismDesktop


class SettingsMixin:
    def _load_settings(self) -> dict:
        try:
            config_path = Path.home() / ".prism" / "prism-desktop.yaml"
            if not config_path.exists():
                return {}
            import yaml
            return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            logger.debug("load settings failed: %s", traceback.format_exc())
            return {}

    def _save_settings(self) -> None:
        try:
            config_path = Path.home() / ".prism" / "prism-desktop.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            import yaml
            config_path.write_text(
                yaml.safe_dump(self._settings, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("save settings failed: %s", traceback.format_exc())
            pass

    def _apply_settings(self) -> None:
        try:
            theme = self._settings.get("theme", "Dark")
            self._apply_theme(theme)
            if hasattr(self, "provider_textfield"):
                provider = self._settings.get("provider", "stepfun")
                self.provider_textfield.value = provider
            if hasattr(self, "base_url_textfield"):
                base_url = self._settings.get("base_url", "https://api.stepfun.com/step_plan/v1")
                self.base_url_textfield.value = base_url
            if hasattr(self, "api_key_textfield"):
                api_key = self._settings.get("api_key", "")
                self.api_key_textfield.value = api_key
            self.page.update()
        except Exception:
            logger.debug("apply settings failed: %s", traceback.format_exc())
            pass
