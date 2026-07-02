"""PRISM Desktop - 浏览器控制逻辑"""
from __future__ import annotations

from typing import TYPE_CHECKING

import flet as ft

from prism.logging import logger
import traceback

if TYPE_CHECKING:
    from prism_desktop.main import PrismDesktop


class BrowserMixin:
    def _browser_open(self) -> None:
        url = self.url_field.value.strip() if hasattr(self, "url_field") else ""
        if not url:
            self._set_status("请输入网址", ft.Colors.RED_400)
            return
        self._append_terminal(f"browser open {url}")
        try:
            from prism.tools.browser import browser as browser_api
            result = browser_api.navigate(url, headless=True)
            if result.get("success"):
                self._set_browser_status(True, result.get("title", url))
                self._append_terminal(f"opened: {result.get('title', url)}")
            else:
                self._set_status(f"打开失败: {result.get('error', 'unknown')}", ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"browser error: {e}")
            self._set_status("浏览器异常", ft.Colors.RED_400)

    def _browser_snapshot(self) -> None:
        self._append_terminal("browser snapshot ...")
        try:
            from prism.tools.browser import browser as browser_api
            result = browser_api.snapshot()
            if result.get("success"):
                self._append(result.get("role", "PRISM"), result.get("content", "(no content)"))
            else:
                self._set_status("快照失败", ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"snapshot error: {e}")

    def _browser_close(self) -> None:
        self._append_terminal("browser close")
        try:
            from prism.tools.browser import browser as browser_api
            browser_api.disconnect()
        except Exception as exc:
            self._log_error("browser disconnect", exc)
        self._set_browser_status(False, "未连接")
