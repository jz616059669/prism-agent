"""PRISM Desktop - 侧边栏逻辑"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import flet as ft

from prism.logging import logger
import traceback

from prism_desktop.i18n import gettext as _

if TYPE_CHECKING:
    from prism_desktop.main import PrismDesktop


class SidebarMixin:
    def _build_sidebar(self) -> ft.Container:
        self._sidebar_container = ft.Container(
            animate=ft.Animation(duration=300, curve=ft.AnimationCurve.EASE_IN_OUT),
            content=ft.Column(
                [
                    ft.Text("PRISM", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    ft.Text("v2.1.4", size=12, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.85),
                ],
                tight=True,
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=300,
            padding=18,
            gradient=ft.LinearGradient(
                colors=[ft.Colors.SURFACE, ft.Colors.SURFACE_CONTAINER],
                begin=ft.Alignment(0, -1),
                end=ft.Alignment(0, 1),
            ),
            bgcolor=ft.Colors.SURFACE,
            border_radius=34,
        )

        save_btn = ft.Button(
            _("save_settings"),
            icon=ft.Icons.SAVE_ROUNDED,
            width=280,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.Padding(18, 14, 18, 14),
                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                color=ft.Colors.ON_PRIMARY_CONTAINER,
            ),
            animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT),
        )
        save_btn.on_click = lambda e: self._save_config()

        browser_deps = self._check_browser_dependencies()
        self._browser_deps_ok = browser_deps.get("playwright") and browser_deps.get("chromium")
        browser_hint = ft.Text(
            "本机未安装 playwright / Chromium，浏览器控制不可用" if not self._browser_deps_ok else "浏览器控制已就绪",
            size=11,
            color=ft.Colors.ON_SURFACE_VARIANT if self._browser_deps_ok else ft.Colors.ERROR,
            opacity=0.9,
        )
        self.url_field = ft.TextField(hint_text="输入网址...", width=280, border_radius=14)
        browser_open_btn = ft.Button(
            "打开网页",
            icon=ft.Icons.LANGUAGE_ROUNDED,
            width=280,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.Padding(18, 14, 18, 14),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                color=ft.Colors.ON_SURFACE,
            ),
            animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT),
            disabled=not self._browser_deps_ok,
        )
        browser_open_btn.on_click = lambda e: self._browser_open()
        browser_snapshot_btn = ft.Button(
            "读取页面快照",
            icon=ft.Icons.ARTICLE_ROUNDED,
            width=280,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.Padding(18, 14, 18, 14),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                color=ft.Colors.ON_SURFACE,
            ),
            animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT),
            disabled=not self._browser_deps_ok,
        )
        browser_snapshot_btn.on_click = lambda e: self._browser_snapshot()
        browser_close_btn = ft.Button(
            _("close_browser"),
            icon=ft.Icons.CLOSE_ROUNDED,
            width=280,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.Padding(18, 14, 18, 14),
                bgcolor=ft.Colors.ERROR_CONTAINER,
                color=ft.Colors.ON_ERROR_CONTAINER,
            ),
            animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT),
            disabled=not self._browser_deps_ok,
        )
        browser_close_btn.on_click = lambda e: self._browser_close()

        # MCP
        self.mcp_refresh_btn = ft.Button(
            _("refresh_mcp"),
            icon=ft.Icons.REFRESH_ROUNDED,
            width=280,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.Padding(18, 14, 18, 14),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                color=ft.Colors.ON_SURFACE,
            ),
            animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT),
        )
        self.mcp_refresh_btn.on_click = lambda e: self._refresh_mcp()
        self.mcp_server_list = ft.Column(spacing=6, tight=True)

        # 会话
        self.session_new_btn = ft.IconButton(
            icon=ft.Icons.ADD_ROUNDED,
            tooltip="新建对话",
            icon_color=ft.Colors.PRIMARY,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.PRIMARY),
            style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY)),
        )
        self.session_new_btn.on_click = lambda e: self._new_session()
        self.session_name_field = ft.TextField(hint_text="会话名称", width=200, border_radius=14)
        self.session_save_btn = ft.Button(
            "保存会话",
            icon=ft.Icons.BOOKMARK_ROUNDED,
            width=120,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=12),
                padding=ft.Padding(18, 14, 18, 14),
                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                color=ft.Colors.ON_PRIMARY_CONTAINER,
            ),
            animate_scale=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_IN_OUT),
        )
        self.session_save_btn.on_click = lambda e: self._save_session()
        self.session_search = ft.TextField(
            hint_text="搜索会话...",
            dense=True,
            border_radius=18,
            height=36,
            content_padding=ft.Padding(10, 8, 10, 8),
        )
        self.session_search.on_change = lambda e: self._filter_sessions(self.session_search.value or "")
        self.session_list = ft.Column(spacing=6, tight=True, scroll=ft.ScrollMode.AUTO)
        self._session_empty_state = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=28, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.5),
                    ft.Container(height=6),
                    ft.Text("暂无会话", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                tight=True,
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(12, 18, 12, 18),
        )

        content = ft.Column(
            [
                browser_hint,
                ft.Container(height=10),
                ft.Text("浏览器控制", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                self.url_field,
                ft.Row([browser_open_btn, browser_snapshot_btn], spacing=8, tight=True),
                browser_close_btn,
                ft.Container(height=12),
                ft.Text("MCP 服务器", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                self.mcp_refresh_btn,
                self.mcp_server_list,
                ft.Container(height=12),
                ft.Text("会话", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Row([self.session_new_btn, self.session_name_field, self.session_save_btn], spacing=8, tight=True),
                self.session_search,
                ft.Container(height=10),
                ft.TextButton(
                    _("restore_layout_defaults"),
                    icon=ft.Icons.UNDO_ROUNDED,
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=12),
                        bgcolor=ft.Colors.SURFACE_CONTAINER,
                        color=ft.Colors.ON_SURFACE,
                    ),
                    on_click=lambda e: self._restore_layout_defaults(),
                ),
                ft.Container(content=self.session_list, expand=True),
                self._session_empty_state,
            ],
            tight=True,
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )

        self._sidebar_container.content = content
        return self._sidebar_container

    def _open_preset_manager(self):
        presets = self._settings.get("model_presets") or {}
        preset_names = list(presets.keys())
        current_preset = self._settings.get("model_preset_name", "")

        def on_dismiss(e):
            pass

        def save_as_preset(e):
            name = preset_name_field.value.strip()
            if not name:
                return
            presets[name] = {
                "model": self.model_dropdown.value,
                "provider": self.provider_textfield.value,
                "base_url": (self.base_url_textfield.value or "").strip(),
                "api_key": self.api_key_textfield.value,
            }
            self._settings["model_presets"] = presets
            self._settings["model_preset_name"] = name
            self._save_settings()
            preset_dlg.open = False
            self.page.update()
            self._refresh_preset_dropdown()
            self._set_status(f"预设已保存：{name}")

        preset_name_field = ft.TextField(hint_text="新预设名称", width=280, border_radius=14)

        preset_buttons = []
        for name in preset_names:
            is_active = name == current_preset

            def apply_preset(e, n=name):
                p = presets.get(n, {})
                if p.get("model"):
                    self.model_dropdown.value = p["model"]
                if p.get("provider"):
                    self.provider_textfield.value = p["provider"]
                if p.get("base_url"):
                    self.base_url_textfield.value = p["base_url"]
                if p.get("api_key"):
                    self.api_key_textfield.value = p["api_key"]
                self._settings["model_preset_name"] = n
                self._save_settings()
                self._set_status(f"已切换预设：{n}")
                preset_dlg.open = False
                self.page.update()

            def delete_preset(e, n=name):
                if n in presets:
                    del presets[n]
                    self._settings["model_presets"] = presets
                    if current_preset == n:
                        self._settings.pop("model_preset_name", None)
                    self._save_settings()
                    preset_dlg.open = False
                    self.page.update()
                    self._refresh_preset_dropdown()
                    self._set_status("预设已删除")

            preset_buttons.append(
                ft.Row(
                    [
                        ft.Text(n, expand=True, color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE),
                        ft.IconButton(
                            ft.Icons.CHECK_CIRCLE_ROUNDED if is_active else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                            tooltip="应用",
                            icon_color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT,
                            on_click=apply_preset,
                        ),
                        ft.IconButton(ft.Icons.DELETE_ROUNDED, tooltip="删除", icon_color=ft.Colors.ERROR, on_click=delete_preset),
                    ],
                    spacing=6,
                    tight=True,
                )
            )

        preset_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("预设管理", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
            bgcolor=ft.Colors.SURFACE,
            content=ft.Column(
                [
                    ft.Text("保存当前配置为新预设：", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Row(
                        [preset_name_field, ft.IconButton(ft.Icons.ADD_ROUNDED, tooltip="保存", icon_color=ft.Colors.PRIMARY, on_click=save_as_preset)],
                        spacing=8,
                        tight=True,
                    ),
                    ft.Container(height=14),
                    ft.Text("已有预设：", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Column(preset_buttons, spacing=6, tight=True, scroll=ft.ScrollMode.AUTO),
                ],
                tight=True,
                spacing=6,
                height=400,
                width=320,
            ),
            actions=[ft.TextButton("关闭", on_click=lambda e: setattr(preset_dlg, 'open', False) or self.page.update())],
        )
        self.page.dialog = preset_dlg
        preset_dlg.open = True
        self.page.update()
        self._append_terminal("preset manager opened")

    def _refresh_preset_dropdown(self):
        # kept for compatibility; actual preset UI is in the dialog
        pass

    def _save_preset(self):
        # kept for compatibility
        pass

    def _restore_layout_defaults(self) -> None:
        self._settings.pop("sidebar_width", None)
        self._settings.pop("sidebar_collapsed", None)
        self._settings.pop("chat_width", None)
        self._settings.pop("right_width", None)
        self._settings.pop("right_collapsed", None)
        self._save_settings()
        self._append_terminal("布局已恢复默认")
        if hasattr(self, "_set_status"):
            self._set_status("布局已重置", ft.Colors.GREEN_400)
        self.page.update()
