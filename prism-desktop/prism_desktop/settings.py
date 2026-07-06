"""PRISM Desktop - 设置面板逻辑"""
from __future__ import annotations

import os
from pathlib import Path
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
            try:
                if hasattr(self, "review_enabled_switch") and self.review_enabled_switch is not None:
                    self._settings["review_enabled"] = bool(self.review_enabled_switch.value)
            except Exception:
                pass
            try:
                if hasattr(self, "review_interval_field") and self.review_interval_field is not None:
                    self._settings["review_interval"] = max(1, int((self.review_interval_field.value or "5").strip() or 5))
            except Exception:
                pass
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
            if hasattr(self, "review_enabled_switch"):
                self.review_enabled_switch.value = bool(self._settings.get("review_enabled", True))
            if hasattr(self, "review_interval_field"):
                self.review_interval_field.value = str(int(self._settings.get("review_interval", 5) or 5))
            self._apply_review_env()
            self.page.update()
        except Exception:
            logger.debug("apply settings failed: %s", traceback.format_exc())
            pass

    def _apply_review_env(self) -> None:
        try:
            enabled = True
            interval = 5
            if hasattr(self, "review_enabled_switch") and self.review_enabled_switch is not None:
                enabled = bool(self.review_enabled_switch.value)
            if hasattr(self, "review_interval_field") and self.review_interval_field is not None:
                try:
                    interval = max(1, int((self.review_interval_field.value or "5").strip() or 5))
                except Exception:
                    interval = 5
            os.environ["PRISM_REVIEW_ENABLED"] = "1" if enabled else "0"
            os.environ["PRISM_REVIEW_INTERVAL"] = str(interval)
        except Exception:
            logger.debug("apply review env failed: %s", traceback.format_exc())

    def _persist_runtime_state(self) -> None:
        try:
            desktop_state_path = Path.home() / ".prism" / "desktop_state.json"
            desktop_state_path.parent.mkdir(parents=True, exist_ok=True)
            state = {
                "current_session": self._current_session_name,
                "unsent_messages": [
                    {
                        "role": getattr(m, "role", "user"),
                        "content": getattr(m, "content", ""),
                        "timestamp": getattr(m, "timestamp", "").isoformat() if hasattr(getattr(m, "timestamp", ""), "isoformat") else str(getattr(m, "timestamp", "")),
                    }
                    for m in getattr(self, "messages", []) or []
                ],
                "chat_draft": getattr(self, "input_field", None).value if hasattr(self, "input_field") else "",
                "sidebar_collapsed": str(self._settings.get("sidebar_collapsed", "false")).lower() == "true",
                "sidebar_width": self._settings.get("sidebar_width"),
                "chat_width": self._settings.get("chat_width"),
                "right_width": self._settings.get("right_width"),
            }
            desktop_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            logger.debug("persist runtime state failed: %s", traceback.format_exc())

    def _restore_runtime_state(self) -> None:
        try:
            desktop_state_path = Path.home() / ".prism" / "desktop_state.json"
            if not desktop_state_path.exists():
                return
            state = json.loads(desktop_state_path.read_text(encoding="utf-8"))
            session_name = state.get("current_session")
            if session_name and getattr(self, "agent", None) and hasattr(self.agent, "load_session"):
                if self.agent.load_session(session_name):
                    self._current_session_name = session_name
                    self.chat_list.controls.clear()
                    if hasattr(self, "_chat_placeholder") and self._chat_placeholder:
                        self._chat_placeholder.visible = False
                    for m in self.agent.messages:
                        if getattr(m, "role", "") == "system":
                            continue
                        role_label = "你" if getattr(m, "role", "") == "user" else ("PRISM" if getattr(m, "role", "") == "assistant" else getattr(m, "role", ""))
                        self._append(role_label, getattr(m, "content", "") or "")
                    self.chat_list.update()
            draft = state.get("chat_draft") or ""
            if draft and hasattr(self, "input_field"):
                self.input_field.value = draft
                if hasattr(self, "_on_input_change"):
                    self._on_input_change()
                self.input_field.update()
        except Exception:
            logger.debug("restore runtime state failed: %s", traceback.format_exc())
