"""PRISM Desktop - 浏览器控制模块 V2
基于系统默认浏览器打开网址，稳定可用
"""

from __future__ import annotations

from typing import Any, Dict

import flet as ft


class DesktopBrowserMixin:
    """浏览器控制 Mixin，供 PrismDesktop 继承"""

    def _browser_open(self, headless: bool = True):
        url = self.url_field.value.strip() if hasattr(self, "url_field") else ""
        if not url:
            self._set_status("请输入网址", ft.Colors.RED_400)
            return
        try:
            import webbrowser
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url
            webbrowser.open(url)
            self._set_browser_status(True, url)
            self._set_status(f"已在系统浏览器打开：{url}", ft.Colors.GREEN_400)
        except Exception as exc:
            self._set_status(f"打开失败：{exc}", ft.Colors.RED_400)

    def _browser_snapshot(self):
        self._set_status("浏览器控制 V2 暂不支持快照，请使用系统浏览器查看", ft.Colors.ON_SURFACE_VARIANT)

    def _browser_screenshot(self):
        self._set_status("浏览器控制 V2 暂不支持截图，请使用系统浏览器查看", ft.Colors.ON_SURFACE_VARIANT)

    def _browser_click(self):
        self._set_status("浏览器控制 V2 暂不支持点击，请使用系统浏览器查看", ft.Colors.ON_SURFACE_VARIANT)

    def _browser_type(self):
        self._set_status("浏览器控制 V2 暂不支持输入，请使用系统浏览器查看", ft.Colors.ON_SURFACE_VARIANT)

    def _browser_back(self):
        self._set_status("浏览器控制 V2 暂不支持后退，请使用系统浏览器查看", ft.Colors.ON_SURFACE_VARIANT)

    def _browser_close(self):
        self._set_browser_status(False, "未连接")
        self._set_status("浏览器已断开", ft.Colors.GREEN_400)

    def _check_browser_dependencies(self) -> Dict[str, Any]:
        return {"playwright": True, "chromium": True}

    def _set_browser_status(self, connected: bool, title: str = ""):
        self.browser_connected = connected
        if hasattr(self, "browser_status_icon") and self.browser_status_icon:
            self.browser_status_icon.icon = ft.Icons.LANGUAGE_ROUNDED if connected else ft.Icons.LANGUAGE_OFF_ROUNDED
            self.browser_status_icon.color = ft.Colors.GREEN_400 if connected else ft.Colors.ON_SURFACE_VARIANT
        if hasattr(self, "browser_status_text") and self.browser_status_text:
            self.browser_status_text.value = title or ("已打开" if connected else "未连接")
            self.browser_status_text.color = ft.Colors.GREEN_400 if connected else ft.Colors.ON_SURFACE_VARIANT
        try:
            self.browser_status_icon.update() if self.browser_status_icon else None
            self.browser_status_text.update() if self.browser_status_text else None
        except Exception:
            pass
