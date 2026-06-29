"""
PRISM Agent - 桌面客户端
基于 Flet 实现，比 Codex CLI 更现代
已连通真实 Agent 后端 + 浏览器控制 + 终端输出 + MCP 控制
"""

import sys
import os
from pathlib import Path
import json
from datetime import datetime
import flet as ft
from typing import Optional
import markdown
import subprocess

# 让桌面端可直接导入上层 prism 包和同目录 prism_desktop 包
REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(REPO_ROOT), str(DESKTOP_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from prism.config import config as prism_config
from prism.agent import create_agent
from prism.tools.browser_bridge import open_page, page_snapshot, close_browser
from prism_desktop import chat as chat_ui
from prism_desktop import settings as settings_ui
from prism_desktop import mcp as mcp_ui
from prism_desktop import system as system_ui


class PrismDesktop:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "PRISM Agent"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 14
        self.page.window_width = 1320
        self.page.window_height = 800
        self.page.theme = ft.Theme(color_scheme_seed="blue", use_material3=True)
        
        self._settings = {}
        
        self.status_text = ft.Text("就绪", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500)
        self._input_accent = None
        self.browser_status_icon = ft.Icon(ft.Icons.LANGUAGE_ROUNDED, size=16, color=ft.Colors.ON_SURFACE_VARIANT)
        self.browser_status_text = ft.Text("就绪", size=11, color=ft.Colors.ON_SURFACE_VARIANT)
        self.browser_connected = None
        self.messages = []
        self.agent = create_agent()
        self.browser_connected = False
        self._terminal_lines = ["PRISM Desktop 已启动"]
        self._mcp_logs = []
        self._skill_list_cache = []
        self._mcp_server_status = {}
        self._current_session_name = None

        self.model_dropdown = ft.Dropdown(
            label="默认模型",
            options=[ft.dropdown.Option("step-3.7-flash"), ft.dropdown.Option("gpt-4o-mini")],
            value=prism_config.get("model.default", "step-3.7-flash") or "step-3.7-flash",
            width=260,
        )
        self.provider_textfield = ft.TextField(label="模型提供商", value=prism_config.get("model.provider", "stepfun") or "stepfun", width=260)
        self.base_url_textfield = ft.TextField(label="Base URL", value=prism_config.get("model.base_url", "https://api.stepfun.com/step_plan/v1") or "https://api.stepfun.com/step_plan/v1", width=260)
        self.api_key_textfield = ft.TextField(label="API Key", password=True, can_reveal_password=True, value=prism_config.get("model.api_key", "") or "", width=260)

        self._format_time = lambda: chat_ui._format_time(self)
        self._markdown_to_ft = lambda text: chat_ui._markdown_to_ft(self, text)
        self._append = lambda *args, **kwargs: chat_ui._append(self, *args, **kwargs)
        self._clear_chat = lambda: chat_ui._clear_chat(self)
        self._show_message_menu = lambda e, target, message_text: chat_ui._show_message_menu(self, e, target, message_text)
        self._send = lambda: chat_ui._send(self)
        self._on_input_change = lambda: chat_ui._on_input_change(self)
        self._load_settings = lambda: settings_ui._load_settings(self)
        self._save_settings = lambda: settings_ui._save_settings(self)
        self._apply_settings = lambda: settings_ui._apply_settings(self)
        self._refresh_mcp = lambda: mcp_ui._refresh_mcp(self)
        self._toggle_mcp_server = lambda name, button: mcp_ui._toggle_mcp_server(self, name, button)
        self._show_mcp_log = lambda name: mcp_ui._show_mcp_log(self, name)
        self._show_mcp_tools = lambda name: mcp_ui._show_mcp_tools(self, name)
        self._bind_tray = lambda: system_ui._bind_tray(self)
        self._bind_context_menu = lambda: system_ui._bind_context_menu(self)
        self._minimize_to_tray = lambda: system_ui._minimize_to_tray(self)
        self._open_config_dir = lambda e: system_ui._open_config_dir(self, e)
        self._open_terminal_here = lambda e: system_ui._open_terminal_here(self, e)
        self._about = lambda e: system_ui._about(self, e)
        self._open_github_releases = lambda e: system_ui._open_github_releases(self, e)

        self._build_ui()
        self._bind_context_menu()
        self._bind_tray()
        # Update clock every second
        def _tick(_):
            self._update_clock()
        self.page.add_periodic_callback(_tick, 1000)
        # Placeholder opacity handled by animate_opacity on show/hide
        self._maybe_show_setup_wizard()
        self._settings = self._load_settings()
        # Load model preset on startup
        presets = (self._settings.get("model_presets") or {})
        current_preset = self._settings.get("model_preset_name", "")
        if current_preset and current_preset in presets:
            p = presets[current_preset]
            if p.get("model"):
                if hasattr(self, "model_dropdown") and self.model_dropdown:
                    self.model_dropdown.value = p["model"]
            if p.get("provider"):
                if hasattr(self, "provider_textfield") and self.provider_textfield:
                    self.provider_textfield.value = p["provider"]
            if p.get("base_url"):
                if hasattr(self, "base_url_textfield") and self.base_url_textfield:
                    self.base_url_textfield.value = p["base_url"]
            if p.get("api_key"):
                if hasattr(self, "api_key_textfield") and self.api_key_textfield:
                    self.api_key_textfield.value = p["api_key"]
        self._apply_settings()

    def _maybe_show_setup_wizard(self):
        try:
            has_key = bool(prism_config.get("model.api_key"))
            has_provider = bool(prism_config.get("model.provider"))
            if has_key and has_provider:
                return
        except Exception:
            pass
        wizard_provider = ft.TextField(label="模型提供商", value="stepfun", width=320)
        wizard_key = ft.TextField(label="API Key", password=True, can_reveal_password=True, width=320)
        wizard_model = ft.TextField(label="默认模型", value="step-3.7-flash", width=320)

        def _save(_):
            try:
                if wizard_provider.value.strip():
                    prism_config.set("model.provider", wizard_provider.value.strip())
                if wizard_key.value.strip():
                    prism_config.set("model.api_key", wizard_key.value.strip())
                if wizard_model.value.strip():
                    prism_config.set("model.default", wizard_model.value.strip())
                self.page.close_dialog()
                self._append_terminal("setup wizard saved")
                self._set_status("配置已保存", ft.Colors.GREEN_400)
            except Exception as e:
                self._set_status(f"保存失败：{e}", ft.Colors.RED_400)

        self.page.dialog = ft.AlertDialog(
            title=ft.Text("首次运行配置向导"),
            content=ft.Column(
                [
                    ft.Text("请先填写模型配置，否则无法正常对话。"),
                    wizard_provider,
                    wizard_key,
                    wizard_model,
                ],
                tight=True,
                spacing=12,
            ),
            actions=[ft.TextButton("保存", on_click=_save)],
        )
        self.page.dialog.open = True
        self.page.update()

    def _bind_context_menu(self) -> None:
        self.page.on_resized = lambda e: self._save_settings()
        self.page.on_window_event = lambda e: self._save_settings()

    def _bind_tray(self) -> None:
        try:
            try:
                import threading
                import pystray
                from PIL import Image, ImageDraw

                def _create_tray_image():
                    img = Image.new("RGB", (64, 64), (0, 0, 0))
                    d = ImageDraw.Draw(img)
                    d.text((16, 16), "P", fill=(255, 255, 255))
                    return img

                def _on_tray_click(icon, item):
                    try:
                        self.page.window_show()
                        if hasattr(self, "input_field"):
                            self.input_field.focus()
                            self.page.update()
                    except Exception:
                        pass

                def _on_exit(icon, item):
                    icon.stop()
                    try:
                        self.page.window_close()
                    except Exception:
                        pass

                menu = pystray.Menu(
                    pystray.MenuItem("打开主窗口", _on_tray_click),
                    pystray.MenuItem("退出", _on_exit),
                )
                icon = pystray.Icon("PRISM", _create_tray_image(), "PRISM Agent", menu)
                t = threading.Thread(target=icon.run, daemon=True)
                t.start()
                self._tray_icon = icon
            except Exception:
                self._tray_icon = None
        except Exception:
            pass

    def _apply_theme(self, name: str):
        name = (name or "Dark").strip()
        if name == "Light":
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.page.theme = ft.Theme(color_scheme_seed="blue", use_material3=True)
        elif name == "Midnight":
            self.page.theme_mode = ft.ThemeMode.DARK
            self.page.theme = ft.Theme(color_scheme_seed="indigo")
        elif name == "Warm":
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.page.theme = ft.Theme(color_scheme_seed="orange")
        else:
            self.page.theme_mode = ft.ThemeMode.DARK
            self.page.theme = ft.Theme(color_scheme_seed="blue", use_material3=True)
        self.page.animate = ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT)
        self.page.update()
        self._append_terminal(f"theme -> {name}")
        self._save_settings()

    def _build_appbar(self) -> ft.AppBar:
        self.title_text = ft.Text("PRISM Agent", size=18, weight=ft.FontWeight.BOLD)
        self.theme_icon_btn = ft.IconButton(icon=ft.Icons.SETTINGS_ROUNDED, tooltip="切换主题", icon_color=ft.Colors.ON_SURFACE_VARIANT)
        self.theme_icon_btn.on_click = lambda e: self._cycle_theme()
        self.minimize_btn = ft.IconButton(icon=ft.Icons.MINIMIZE_ROUNDED, tooltip="最小化到托盘", icon_color=ft.Colors.ON_SURFACE_VARIANT)
        self.minimize_btn.on_click = lambda e: self._minimize_to_tray()
        self.about_btn = ft.IconButton(icon=ft.Icons.INFO_ROUNDED, tooltip="关于", icon_color=ft.Colors.ON_SURFACE_VARIANT)
        self.about_btn.on_click = lambda e: self._about(e)
        self.sidebar_toggle_btn = ft.IconButton(icon=ft.Icons.MENU_ROUNDED, tooltip="切换侧边栏", icon_color=ft.Colors.ON_SURFACE_VARIANT)
        self.sidebar_toggle_btn.on_click = lambda e: self._toggle_sidebar()
        return ft.AppBar(
            title=self.title_text,
            actions=[
                self.sidebar_toggle_btn,
                self.theme_icon_btn,
                self.minimize_btn,
                self.about_btn,
            ],
            elevation=4,
            bgcolor=ft.Colors.SURFACE,
        )

    def _toggle_sidebar(self):
        if not hasattr(self, "_sidebar_container"):
            return
        visible = self._sidebar_container.visible
        self._sidebar_container.visible = not visible
        width = 0 if visible else 280
        self._sidebar_container.width = width
        self._sidebar_container.animate = ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT)
        self._sidebar_container.update()
        self._settings["sidebar_collapsed"] = not visible
        self._save_settings()
        self.page.update()

    def _animate_sidebar_cards(self):
        import time
        time.sleep(0.1)
        for card in self._sidebar_container.content.controls:
            if hasattr(card, 'animate_opacity'):
                card.opacity = 1
                card.update()
                time.sleep(0.05)

    def _cycle_theme(self):
        current = self._settings.get("theme", "Dark")
        themes = ["Dark", "Light", "Midnight", "Warm"]
        idx = themes.index(current) if current in themes else 0
        next_theme = themes[(idx + 1) % len(themes)]
        self._settings["theme"] = next_theme
        if hasattr(self, "theme_dropdown") and self.theme_dropdown is not None:
            self.theme_dropdown.value = next_theme
        self._apply_theme(next_theme)

    def _minimize_to_tray(self):
        try:
            self.page.window_hide()
            self._append_terminal("minimized to tray")
        except Exception:
            pass

    def _build_ui(self):
        self._clock_text = ft.Text(datetime.now().strftime("%H:%M:%S"), size=10, color=ft.Colors.ON_SURFACE_VARIANT)
        self.page.appbar = self._build_appbar()
        self._chat_container = ft.Container(self._build_chat(), expand=True)
        self._right_container = ft.Container(self._build_right_panel(), expand=True)
        sidebar = self._build_sidebar()
        if str(self._settings.get("sidebar_collapsed", "false")).lower() == "true":
            sidebar.visible = False
            sidebar.width = 0
            sidebar.padding = 0
        if isinstance(self._settings.get("sidebar_width"), int):
            sidebar.width = int(self._settings.get("sidebar_width"))
        if isinstance(self._settings.get("chat_width"), int):
            self._chat_container.width = int(self._settings.get("chat_width"))
        if isinstance(self._settings.get("right_width"), int):
            self._right_container.width = int(self._settings.get("right_width"))
        self.page.add(
            ft.Row(
                [
                    sidebar,
                    ft.VerticalDivider(width=1),
                    self._chat_container,
                    ft.VerticalDivider(width=1),
                    self._right_container,
                ],
                expand=True,
                spacing=0,
            )
        )
    
    def _open_preset_manager(self):
        presets = (self._settings.get("model_presets") or {})
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

        preset_name_field = ft.TextField(hint_text="新预设名称", width=260, border_radius=8)

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
                    self._set_status(f"预设已删除：{n}")

            preset_buttons.append(
                ft.Row([
                    ft.Text(n, expand=True, color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE),
                    ft.IconButton(ft.Icons.CHECK_CIRCLE_ROUNDED if is_active else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED, tooltip="应用", icon_color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT, on_click=apply_preset),
                    ft.IconButton(ft.Icons.DELETE_ROUNDED, tooltip="删除", icon_color=ft.Colors.ERROR, on_click=delete_preset),
                ], spacing=6, tight=True)
            )

        preset_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("预设管理"),
            content=ft.Column([
                ft.Text("保存当前配置为新预设：", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Row([preset_name_field, ft.IconButton(ft.Icons.ADD_ROUNDED, tooltip="保存", icon_color=ft.Colors.PRIMARY, on_click=save_as_preset)], spacing=8, tight=True),
                ft.Container(height=8),
                ft.Text("已有预设：", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Column(preset_buttons, spacing=4, tight=True, scroll=ft.ScrollMode.AUTO),
            ], tight=True, spacing=4, height=400, width=300),
            actions=[ft.TextButton("关闭", on_click=lambda e: setattr(preset_dlg, 'open', False) or self.page.update())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = preset_dlg
        preset_dlg.open = True
        self.page.update()

    def _refresh_preset_dropdown(self):
        presets = (self._settings.get("model_presets") or {})
        preset_names = list(presets.keys())
        current = self._settings.get("model_preset_name", "")
        if hasattr(self, "model_dropdown"):
            self.model_dropdown.options = [ft.dropdown.Option(n) for n in preset_names] if preset_names else []
            if current and current in preset_names:
                self.model_dropdown.value = current
            elif preset_names:
                self.model_dropdown.value = preset_names[0]
            else:
                self.model_dropdown.value = ""
            self.model_dropdown.update()

    def _save_preset(self):
        name = self.model_dropdown.value
        if not name:
            self._set_status("请先选择或输入预设名称", ft.Colors.RED_400)
            return
        presets = (self._settings.get("model_presets") or {})
        presets[name] = {
            "model": self.model_dropdown.value,
            "provider": self.provider_textfield.value,
            "base_url": (self.base_url_textfield.value or "").strip(),
            "api_key": self.api_key_textfield.value,
        }
        self._settings["model_presets"] = presets
        self._settings["model_preset_name"] = name
        self._save_settings()
        self._set_status(f"预设已保存：{name}")

    def _build_sidebar(self) -> ft.Container:
        self._sidebar_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text("PRISM", size=20, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=12, color=ft.Colors.TRANSPARENT),
                ],
                tight=True,
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=280,
            padding=16,
            gradient=ft.LinearGradient(
                colors=[ft.Colors.SURFACE, ft.Colors.SURFACE_CONTAINER],
                begin=ft.Alignment(0, -1),
                end=ft.Alignment(0, 1),
            ),
            bgcolor=ft.Colors.SURFACE,
            border_radius=12,
        )

        save_btn = ft.Button("保存配置", icon=ft.Icons.SAVE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        save_btn.on_click = lambda e: self._save_config()

        self.url_field = ft.TextField(hint_text="输入网址...", width=260, border_radius=8)
        browser_open_btn = ft.Button("打开网页", icon=ft.Icons.LANGUAGE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        browser_open_btn.on_click = lambda e: self._browser_open()
        browser_snapshot_btn = ft.Button("读取页面快照", icon=ft.Icons.ARTICLE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        browser_snapshot_btn.on_click = lambda e: self._browser_snapshot()
        browser_close_btn = ft.Button("关闭浏览器", icon=ft.Icons.CLOSE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        browser_close_btn.on_click = lambda e: self._browser_close()

        # MCP
        self.mcp_refresh_btn = ft.Button("刷新 MCP 服务器", icon=ft.Icons.REFRESH_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        self.mcp_refresh_btn.on_click = lambda e: self._refresh_mcp()
        self.mcp_server_list = ft.Column(spacing=4, tight=True)

        # Skills
        self.skill_refresh_btn = ft.Button("刷新 Skills", icon=ft.Icons.REFRESH_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        self.skill_refresh_btn.on_click = lambda e: self._refresh_skills()
        self.skill_install_field = ft.TextField(hint_text="安装 Skill 名称或本地路径", width=260, border_radius=8)
        self.skill_install_btn = ft.Button("安装 Skill", icon=ft.Icons.DOWNLOAD_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        self.skill_install_btn.on_click = lambda e: self._install_skill_from_ui()
        self.skill_list = ft.Column(spacing=4, tight=True)

        # 会话
        self.session_new_btn = ft.IconButton(icon=ft.Icons.ADD_ROUNDED, tooltip="新建对话", icon_color=ft.Colors.ON_SURFACE_VARIANT, ink=True)
        self.session_new_btn.on_click = lambda e: self._new_session()
        self.session_name_field = ft.TextField(hint_text="会话名称", width=200, border_radius=8)
        self.session_save_btn = ft.Button("保存会话", icon=ft.Icons.BOOKMARK_ROUNDED, width=120, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(12, 10, 12, 10)))
        self.session_save_btn.on_click = lambda e: self._save_session()
        self.session_list = ft.Column(spacing=4, tight=True)
        self._session_empty_text = ft.Text("暂无保存的会话", size=11, color=ft.Colors.ON_SURFACE_VARIANT)

        sidebar_content = self._sidebar_container.content
        sidebar_content.controls.extend([
            ft.Container(
                content=ft.Column([
                    ft.Text("模型配置", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    # Preset selector
                    ft.Row([
                        self.model_dropdown,
                        ft.IconButton(icon=ft.Icons.BOOKMARK_ROUNDED, tooltip="保存为预设", icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self._save_preset()),
                    ], spacing=6, tight=True),
                    ft.Container(height=4),
                    self.provider_textfield,
                    ft.Container(height=4),
                    self.base_url_textfield,
                    ft.Container(height=4),
                    self.api_key_textfield,
                    ft.Container(height=8),
                    ft.Row([
                        save_btn,
                        ft.TextButton("预设管理", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)), on_click=lambda e: self._open_preset_manager()),
                    ], spacing=8, tight=True),
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                ink=True,
            ),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    ft.Text("浏览器控制", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    self.url_field,
                    ft.Row([browser_open_btn, browser_snapshot_btn, browser_close_btn], spacing=6, wrap=True),
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            ),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    ft.Text("MCP 控制", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    self.mcp_refresh_btn,
                    ft.Container(height=4),
                    ft.Text("已配置服务器", size=10, color=ft.Colors.ON_SURFACE),
                    self.mcp_server_list,
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                ink=True,
            ),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    ft.Text("Skills", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    self.skill_refresh_btn,
                    self.skill_install_field,
                    ft.Container(height=4),
                    self.skill_install_btn,
                    ft.Container(height=4),
                    ft.Text("可用 Skills", size=10, color=ft.Colors.ON_SURFACE),
                    self.skill_list,
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            ),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    ft.Text("会话", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    ft.Row([self.session_name_field, self.session_save_btn], spacing=6),
                    ft.Container(height=4),
                    ft.Text("已保存会话", size=10, color=ft.Colors.ON_SURFACE),
                    ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT, opacity=0.5),
                    self.session_list,
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                ink=True,
            ),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    ft.Text("状态", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    ft.Row([self.browser_status_icon, self.browser_status_text], spacing=8, alignment=ft.MainAxisAlignment.START),
                    ft.Row([self.status_text, ft.Container(expand=True), self._clock_text], spacing=8),
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                ink=True,
            ),
        ])
        return self._sidebar_container

    def _build_chat(self) -> ft.Column:
        self.chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True, scroll=ft.ScrollMode.AUTO)
        self.input_field = ft.TextField(
            hint_text="输入消息...",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=6,
            shift_enter=True,
            border_radius=10,
            focused_border_color=ft.Colors.PRIMARY,
            focused_border_width=2,
            border_color=ft.Colors.OUTLINE_VARIANT,
            suffix=ft.IconButton(icon=ft.Icons.CLEAR_ROUNDED, tooltip="清空", icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self.input_field.clear()),
        )
        self.input_count = ft.Text("0 字", size=11, color=ft.Colors.ON_SURFACE)
        self.input_field.on_change = lambda e: self._on_input_change()
        self.send_btn = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, tooltip="发送", bgcolor=ft.Colors.PRIMARY, icon_color=ft.Colors.ON_PRIMARY, animate_scale=True, scale=1.0, disabled=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), ink=True)
        self.send_btn.on_click = lambda e: self._send()
        self.input_field.on_change = lambda e: self._on_input_change()
        accent = self._input_accent
        self.input_field.on_focus = lambda e: (setattr(self.send_btn, 'scale', 1.1), self.send_btn.update(), setattr(accent, 'bgcolor', ft.Colors.PRIMARY), accent.update())
        self.input_field.on_blur = lambda e: (setattr(self.send_btn, 'scale', 1.0), self.send_btn.update(), setattr(accent, 'bgcolor', ft.Colors.TRANSPARENT), accent.update())
        self.stop_btn = ft.IconButton(icon=ft.Icons.STOP_ROUNDED, tooltip="停止生成", visible=False, bgcolor=ft.Colors.ERROR_CONTAINER, icon_color=ft.Colors.ON_ERROR_CONTAINER, ink=True)
        self.stop_btn.on_click = lambda e: self._stop_send()
        self.input_field.on_submit = lambda e: self._send()
        clear_chat_btn = ft.TextButton("清屏", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6), bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER), icon=ft.Icons.DELETE_OUTLINE_ROUNDED)
        clear_chat_btn.on_click = lambda e: self._clear_chat()
        
        self._chat_placeholder = ft.Column(
            [
                ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.4),
                ft.Container(height=12),
                ft.Text("输入消息开始对话", size=13, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER, opacity=0.6),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.Column(
            [
                ft.Text("对话", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(height=2, color=ft.Colors.OUTLINE_VARIANT),
                ft.Stack(
                    [
                        self.chat_list,
                        ft.Container(
                            content=self._chat_placeholder,
                            alignment=ft.Alignment(0, 0),
                            expand=True,
                        ),
                    ],
                    expand=True,
                ),
                ft.Divider(height=2, color=ft.Colors.OUTLINE_VARIANT),
                ft.Container(
                    content=ft.Row([self.input_field, self.send_btn, self.stop_btn], spacing=8, expand=True),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=12,
                    padding=ft.Padding(12, 8, 12, 8),
                    border=ft.Border(bottom=ft.border.BorderSide(2.0, ft.Colors.OUTLINE_VARIANT)),
                    shadow=ft.BoxShadow(blur_radius=8, spread_radius=0, color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    animate_border_color=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
                ),
                ft.Container(
                    height=2,
                    bgcolor=ft.Colors.TRANSPARENT,
                    animate_bgcolor=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
                ),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                ft.Row([clear_chat_btn, self.input_count], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text("Enter 发送 / Shift+Enter 换行", size=10, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.7),
            ],
            expand=True,
            spacing=6,
        )
    
    def _build_right_panel(self) -> ft.Column:
        self.terminal_input = ft.TextField(
            hint_text="输入终端命令...",
            expand=True,
            min_lines=1,
            max_lines=3,
            shift_enter=True,
            border_radius=8,
            focused_border_color=ft.Colors.PRIMARY,
            focused_border_width=2,
            border_color=ft.Colors.OUTLINE_VARIANT,
            suffix=ft.IconButton(icon=ft.Icons.CLEAR_ROUNDED, tooltip="清空", icon_size=16, icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self.terminal_input.clear()),
        )
        terminal_run_btn = ft.IconButton(icon=ft.Icons.PLAY_ARROW_ROUNDED, tooltip="执行命令", icon_color=ft.Colors.ON_SURFACE_VARIANT, ink=True)
        terminal_run_btn.on_click = lambda e: self._run_terminal_command()
        self.terminal_input.on_submit = lambda e: self._run_terminal_command()
        self.terminal_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO)
        self.mcp_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO)
        
        clear_terminal_btn = ft.TextButton("清空终端", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6), bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER), icon=ft.Icons.DELETE_OUTLINE_ROUNDED, ink=True)
        clear_terminal_btn.on_click = lambda e: self._clear_terminal()
        clear_mcp_btn = ft.TextButton("清空 MCP", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6), bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER), icon=ft.Icons.DELETE_OUTLINE_ROUNDED, ink=True)
        clear_mcp_btn.on_click = lambda e: self._clear_mcp()
        
        terminal_tab = ft.Column(
            [
                ft.Row([self.terminal_input, terminal_run_btn], spacing=8),
                ft.Row([clear_terminal_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(self.terminal_list, expand=True, border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), left=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), right=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)), border_radius=12, padding=12, bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        mcp_tab = ft.Column(
            [
                ft.Row([clear_mcp_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(self.mcp_list, expand=True, border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), left=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), right=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)), border_radius=12, padding=12, bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self._right_terminal_tab = terminal_tab
        self._right_mcp_tab = mcp_tab
        self._right_tab_content = ft.Column(
            [
                terminal_tab,
                mcp_tab,
            ],
            expand=True,
        )
        self.right_tabs = ft.Tabs(
            content=self._right_tab_content,
            selected_index=0,
            on_change=lambda e: None,
            expand=True,
            tab_alignment=ft.TabAlignment.START,
        )
        return ft.Column(
            [
                self.right_tabs,
            ],
            expand=True,
            spacing=8,
        )
    
    def _append(self, role: str, text: str, retry: bool = False, retry_text: str = "", placeholder: bool = False):
        if hasattr(self, "_chat_placeholder") and self._chat_placeholder and self._chat_placeholder in self.chat_list.controls:
            self.chat_list.controls.remove(self._chat_placeholder)
        is_user = role == "你"
        align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        text_color = ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M")

        try:
            import markdown
            rendered = markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br"])
        except Exception:
            rendered = text

        is_error = not is_user and (text.startswith("Error:") or text.startswith("请求超时") or text.startswith("失败"))
        display_color = ft.Colors.ERROR if is_error else text_color

        if is_user:
            content_widget = ft.Column(
                [
                    self._markdown_to_ft(rendered),
                    ft.Text(timestamp, size=10, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.END),
                ],
                tight=True,
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.END,
            )
        else:
            content_widget = ft.Column(
                [
                    self._markdown_to_ft(rendered),
                    ft.Text(timestamp, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                tight=True,
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            )

        message_row = ft.Row(
            [content_widget],
            alignment=align,
            expand=True,
        )

        self.chat_list.controls.append(message_row)
        
        # Retry button for error messages
        if is_error and retry_text:
            retry_btn = ft.TextButton(
                "重试",
                icon=ft.Icons.REFRESH_ROUNDED,
                style=ft.ButtonStyle(color=ft.Colors.ERROR),
                on_click=lambda e, t=retry_text: self._send(t),
            )
            retry_row = ft.Row(
                [retry_btn],
                alignment=ft.MainAxisAlignment.START,
                expand=True,
            )
            self.chat_list.controls.append(retry_row)
        
        max_chat_items = 500
        if len(self.chat_list.controls) > max_chat_items:
            self.chat_list.controls = self.chat_list.controls[-max_chat_items:]
        self.chat_list.scroll_to(offset=-1, duration=200)
        self.chat_list.update()
        return message_row
    def _build_appbar(self) -> ft.AppBar:
        self.title_text = ft.Text("PRISM Agent", size=18, weight=ft.FontWeight.BOLD)
        self.theme_icon_btn = ft.IconButton(icon=ft.Icons.SETTINGS_ROUNDED, tooltip="切换主题", icon_color=ft.Colors.ON_SURFACE_VARIANT)
        self.theme_icon_btn.on_click = lambda e: self._cycle_theme()
        self.minimize_btn = ft.IconButton(icon=ft.Icons.MINIMIZE_ROUNDED, tooltip="最小化到托盘", icon_color=ft.Colors.ON_SURFACE_VARIANT)
        self.minimize_btn.on_click = lambda e: self._minimize_to_tray()
        self.about_btn = ft.IconButton(icon=ft.Icons.INFO_ROUNDED, tooltip="关于", icon_color=ft.Colors.ON_SURFACE_VARIANT)
        self.about_btn.on_click = lambda e: self._about(e)
        self.sidebar_toggle_btn = ft.IconButton(icon=ft.Icons.MENU_ROUNDED, tooltip="切换侧边栏", icon_color=ft.Colors.ON_SURFACE_VARIANT)
        self.sidebar_toggle_btn.on_click = lambda e: self._toggle_sidebar()
        return ft.AppBar(
            title=self.title_text,
            actions=[
                self.sidebar_toggle_btn,
                self.theme_icon_btn,
                self.minimize_btn,
                self.about_btn,
            ],
            elevation=4,
            bgcolor=ft.Colors.SURFACE,
        )

    def _toggle_sidebar(self):
        if not hasattr(self, "_sidebar_container"):
            return
        visible = self._sidebar_container.visible
        self._sidebar_container.visible = not visible
        width = 0 if visible else 280
        self._sidebar_container.width = width
        self._sidebar_container.animate = ft.Animation(300, ft.AnimationCurve.EASE_IN_OUT)
        self._sidebar_container.update()
        self._settings["sidebar_collapsed"] = not visible
        self._save_settings()
        self.page.update()

    def _animate_sidebar_cards(self):
        import time
        time.sleep(0.1)
        for card in self._sidebar_container.content.controls:
            if hasattr(card, 'animate_opacity'):
                card.opacity = 1
                card.update()
                time.sleep(0.05)

    def _cycle_theme(self):
        current = self._settings.get("theme", "Dark")
        themes = ["Dark", "Light", "Midnight", "Warm"]
        idx = themes.index(current) if current in themes else 0
        next_theme = themes[(idx + 1) % len(themes)]
        self._settings["theme"] = next_theme
        if hasattr(self, "theme_dropdown") and self.theme_dropdown is not None:
            self.theme_dropdown.value = next_theme
        self._apply_theme(next_theme)

    def _minimize_to_tray(self):
        try:
            self.page.window_hide()
            self._append_terminal("minimized to tray")
        except Exception:
            pass

    def _build_ui(self):
        self._clock_text = ft.Text(datetime.now().strftime("%H:%M:%S"), size=10, color=ft.Colors.ON_SURFACE_VARIANT)
        self.page.appbar = self._build_appbar()
        self._chat_container = ft.Container(self._build_chat(), expand=True)
        self._right_container = ft.Container(self._build_right_panel(), expand=True)
        sidebar = self._build_sidebar()
        if str(self._settings.get("sidebar_collapsed", "false")).lower() == "true":
            sidebar.visible = False
            sidebar.width = 0
            sidebar.padding = 0
        if isinstance(self._settings.get("sidebar_width"), int):
            sidebar.width = int(self._settings.get("sidebar_width"))
        if isinstance(self._settings.get("chat_width"), int):
            self._chat_container.width = int(self._settings.get("chat_width"))
        if isinstance(self._settings.get("right_width"), int):
            self._right_container.width = int(self._settings.get("right_width"))
        self.page.add(
            ft.Row(
                [
                    sidebar,
                    ft.VerticalDivider(width=1),
                    self._chat_container,
                    ft.VerticalDivider(width=1),
                    self._right_container,
                ],
                expand=True,
                spacing=0,
            )
        )
    
    def _open_preset_manager(self):
        presets = (self._settings.get("model_presets") or {})
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

        preset_name_field = ft.TextField(hint_text="新预设名称", width=260, border_radius=8)

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
                    self._set_status(f"预设已删除：{n}")

            preset_buttons.append(
                ft.Row([
                    ft.Text(n, expand=True, color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE),
                    ft.IconButton(ft.Icons.CHECK_CIRCLE_ROUNDED if is_active else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED, tooltip="应用", icon_color=ft.Colors.PRIMARY if is_active else ft.Colors.ON_SURFACE_VARIANT, on_click=apply_preset),
                    ft.IconButton(ft.Icons.DELETE_ROUNDED, tooltip="删除", icon_color=ft.Colors.ERROR, on_click=delete_preset),
                ], spacing=6, tight=True)
            )

        preset_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("预设管理"),
            content=ft.Column([
                ft.Text("保存当前配置为新预设：", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Row([preset_name_field, ft.IconButton(ft.Icons.ADD_ROUNDED, tooltip="保存", icon_color=ft.Colors.PRIMARY, on_click=save_as_preset)], spacing=8, tight=True),
                ft.Container(height=8),
                ft.Text("已有预设：", size=12, color=ft.Colors.ON_SURFACE_VARIANT),
                ft.Column(preset_buttons, spacing=4, tight=True, scroll=ft.ScrollMode.AUTO),
            ], tight=True, spacing=4, height=400, width=300),
            actions=[ft.TextButton("关闭", on_click=lambda e: setattr(preset_dlg, 'open', False) or self.page.update())],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = preset_dlg
        preset_dlg.open = True
        self.page.update()

    def _refresh_preset_dropdown(self):
        presets = (self._settings.get("model_presets") or {})
        preset_names = list(presets.keys())
        current = self._settings.get("model_preset_name", "")
        if hasattr(self, "model_dropdown"):
            self.model_dropdown.options = [ft.dropdown.Option(n) for n in preset_names] if preset_names else []
            if current and current in preset_names:
                self.model_dropdown.value = current
            elif preset_names:
                self.model_dropdown.value = preset_names[0]
            else:
                self.model_dropdown.value = ""
            self.model_dropdown.update()

    def _save_preset(self):
        name = self.model_dropdown.value
        if not name:
            self._set_status("请先选择或输入预设名称", ft.Colors.RED_400)
            return
        presets = (self._settings.get("model_presets") or {})
        presets[name] = {
            "model": self.model_dropdown.value,
            "provider": self.provider_textfield.value,
            "base_url": (self.base_url_textfield.value or "").strip(),
            "api_key": self.api_key_textfield.value,
        }
        self._settings["model_presets"] = presets
        self._settings["model_preset_name"] = name
        self._save_settings()
        self._set_status(f"预设已保存：{name}")

    def _build_sidebar(self) -> ft.Container:
        self._sidebar_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text("PRISM", size=20, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=12, color=ft.Colors.TRANSPARENT),
                ],
                tight=True,
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=280,
            padding=16,
            gradient=ft.LinearGradient(
                colors=[ft.Colors.SURFACE, ft.Colors.SURFACE_CONTAINER],
                begin=ft.Alignment(0, -1),
                end=ft.Alignment(0, 1),
            ),
            bgcolor=ft.Colors.SURFACE,
            border_radius=12,
        )

        save_btn = ft.Button("保存配置", icon=ft.Icons.SAVE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        save_btn.on_click = lambda e: self._save_config()

        self.url_field = ft.TextField(hint_text="输入网址...", width=260, border_radius=8)
        browser_open_btn = ft.Button("打开网页", icon=ft.Icons.LANGUAGE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        browser_open_btn.on_click = lambda e: self._browser_open()
        browser_snapshot_btn = ft.Button("读取页面快照", icon=ft.Icons.ARTICLE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        browser_snapshot_btn.on_click = lambda e: self._browser_snapshot()
        browser_close_btn = ft.Button("关闭浏览器", icon=ft.Icons.CLOSE_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        browser_close_btn.on_click = lambda e: self._browser_close()

        # MCP
        self.mcp_refresh_btn = ft.Button("刷新 MCP 服务器", icon=ft.Icons.REFRESH_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        self.mcp_refresh_btn.on_click = lambda e: self._refresh_mcp()
        self.mcp_server_list = ft.Column(spacing=4, tight=True)

        # Skills
        self.skill_refresh_btn = ft.Button("刷新 Skills", icon=ft.Icons.REFRESH_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        self.skill_refresh_btn.on_click = lambda e: self._refresh_skills()
        self.skill_install_field = ft.TextField(hint_text="安装 Skill 名称或本地路径", width=260, border_radius=8)
        self.skill_install_btn = ft.Button("安装 Skill", icon=ft.Icons.DOWNLOAD_ROUNDED, width=260, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(16, 12, 16, 12)))
        self.skill_install_btn.on_click = lambda e: self._install_skill_from_ui()
        self.skill_list = ft.Column(spacing=4, tight=True)

        # 会话
        self.session_new_btn = ft.IconButton(icon=ft.Icons.ADD_ROUNDED, tooltip="新建对话", icon_color=ft.Colors.ON_SURFACE_VARIANT, ink=True)
        self.session_new_btn.on_click = lambda e: self._new_session()
        self.session_name_field = ft.TextField(hint_text="会话名称", width=200, border_radius=8)
        self.session_save_btn = ft.Button("保存会话", icon=ft.Icons.BOOKMARK_ROUNDED, width=120, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=ft.Padding(12, 10, 12, 10)))
        self.session_save_btn.on_click = lambda e: self._save_session()
        self.session_list = ft.Column(spacing=4, tight=True)
        self._session_empty_text = ft.Text("暂无保存的会话", size=11, color=ft.Colors.ON_SURFACE_VARIANT)

        sidebar_content = self._sidebar_container.content
        sidebar_content.controls.extend([
            ft.Container(
                content=ft.Column([
                    ft.Text("模型配置", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    # Preset selector
                    ft.Row([
                        self.model_dropdown,
                        ft.IconButton(icon=ft.Icons.BOOKMARK_ROUNDED, tooltip="保存为预设", icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self._save_preset()),
                    ], spacing=6, tight=True),
                    ft.Container(height=4),
                    self.provider_textfield,
                    ft.Container(height=4),
                    self.base_url_textfield,
                    ft.Container(height=4),
                    self.api_key_textfield,
                    ft.Container(height=8),
                    ft.Row([
                        save_btn,
                        ft.TextButton("预设管理", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6)), on_click=lambda e: self._open_preset_manager()),
                    ], spacing=8, tight=True),
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                ink=True,
            ),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    ft.Text("浏览器控制", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    self.url_field,
                    ft.Row([browser_open_btn, browser_snapshot_btn, browser_close_btn], spacing=6, wrap=True),
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            ),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    ft.Text("MCP 控制", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    self.mcp_refresh_btn,
                    ft.Container(height=4),
                    ft.Text("已配置服务器", size=10, color=ft.Colors.ON_SURFACE),
                    self.mcp_server_list,
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                ink=True,
            ),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    ft.Text("Skills", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    self.skill_refresh_btn,
                    self.skill_install_field,
                    ft.Container(height=4),
                    self.skill_install_btn,
                    ft.Container(height=4),
                    ft.Text("可用 Skills", size=10, color=ft.Colors.ON_SURFACE),
                    self.skill_list,
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)),
            ),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    ft.Text("会话", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    ft.Row([self.session_name_field, self.session_save_btn], spacing=6),
                    ft.Container(height=4),
                    ft.Text("已保存会话", size=10, color=ft.Colors.ON_SURFACE),
                    ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT, opacity=0.5),
                    self.session_list,
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                ink=True,
            ),
            ft.Container(height=12),
            ft.Container(
                content=ft.Column([
                    ft.Text("状态", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE),
                    ft.Container(height=6),
                    ft.Row([self.browser_status_icon, self.browser_status_text], spacing=8, alignment=ft.MainAxisAlignment.START),
                    ft.Row([self.status_text, ft.Container(expand=True), self._clock_text], spacing=8),
                ], tight=True, spacing=4),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=10,
                padding=10,
                ink=True,
            ),
        ])
        return self._sidebar_container

    def _build_chat(self) -> ft.Column:
        self.chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True, scroll=ft.ScrollMode.AUTO)
        self.input_field = ft.TextField(
            hint_text="输入消息...",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=6,
            shift_enter=True,
            border_radius=10,
            focused_border_color=ft.Colors.PRIMARY,
            focused_border_width=2,
            border_color=ft.Colors.OUTLINE_VARIANT,
            suffix=ft.IconButton(icon=ft.Icons.CLEAR_ROUNDED, tooltip="清空", icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self.input_field.clear()),
        )
        self.input_count = ft.Text("0 字", size=11, color=ft.Colors.ON_SURFACE)
        self.input_field.on_change = lambda e: self._on_input_change()
        self.send_btn = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, tooltip="发送", bgcolor=ft.Colors.PRIMARY, icon_color=ft.Colors.ON_PRIMARY, animate_scale=True, scale=1.0, disabled=True, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)), ink=True)
        self.send_btn.on_click = lambda e: self._send()
        self.input_field.on_change = lambda e: self._on_input_change()
        accent = self._input_accent
        self.input_field.on_focus = lambda e: (setattr(self.send_btn, 'scale', 1.1), self.send_btn.update(), setattr(accent, 'bgcolor', ft.Colors.PRIMARY), accent.update())
        self.input_field.on_blur = lambda e: (setattr(self.send_btn, 'scale', 1.0), self.send_btn.update(), setattr(accent, 'bgcolor', ft.Colors.TRANSPARENT), accent.update())
        self.stop_btn = ft.IconButton(icon=ft.Icons.STOP_ROUNDED, tooltip="停止生成", visible=False, bgcolor=ft.Colors.ERROR_CONTAINER, icon_color=ft.Colors.ON_ERROR_CONTAINER, ink=True)
        self.stop_btn.on_click = lambda e: self._stop_send()
        self.input_field.on_submit = lambda e: self._send()
        clear_chat_btn = ft.TextButton("清屏", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6), bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER), icon=ft.Icons.DELETE_OUTLINE_ROUNDED)
        clear_chat_btn.on_click = lambda e: self._clear_chat()
        
        self._chat_placeholder = ft.Column(
            [
                ft.Icon(ft.Icons.CHAT_BUBBLE_OUTLINE_ROUNDED, size=48, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.4),
                ft.Container(height=12),
                ft.Text("输入消息开始对话", size=13, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.CENTER, opacity=0.6),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        return ft.Column(
            [
                ft.Text("对话", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(height=2, color=ft.Colors.OUTLINE_VARIANT),
                ft.Stack(
                    [
                        self.chat_list,
                        ft.Container(
                            content=self._chat_placeholder,
                            alignment=ft.Alignment(0, 0),
                            expand=True,
                        ),
                    ],
                    expand=True,
                ),
                ft.Divider(height=2, color=ft.Colors.OUTLINE_VARIANT),
                ft.Container(
                    content=ft.Row([self.input_field, self.send_btn, self.stop_btn], spacing=8, expand=True),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    border_radius=12,
                    padding=ft.Padding(12, 8, 12, 8),
                    border=ft.Border(bottom=ft.border.BorderSide(2.0, ft.Colors.OUTLINE_VARIANT)),
                    shadow=ft.BoxShadow(blur_radius=8, spread_radius=0, color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)),
                    animate_border_color=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
                ),
                ft.Container(
                    height=2,
                    bgcolor=ft.Colors.TRANSPARENT,
                    animate_bgcolor=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
                ),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                ft.Row([clear_chat_btn, self.input_count], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Text("Enter 发送 / Shift+Enter 换行", size=10, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.7),
            ],
            expand=True,
            spacing=8,
        )
    
    def _build_right_panel(self) -> ft.Column:
        self.terminal_input = ft.TextField(
            hint_text="输入终端命令...",
            expand=True,
            min_lines=1,
            max_lines=3,
            shift_enter=True,
            border_radius=8,
            focused_border_color=ft.Colors.PRIMARY,
            focused_border_width=2,
            border_color=ft.Colors.OUTLINE_VARIANT,
            suffix=ft.IconButton(icon=ft.Icons.CLEAR_ROUNDED, tooltip="清空", icon_size=16, icon_color=ft.Colors.ON_SURFACE_VARIANT, on_click=lambda e: self.terminal_input.clear()),
        )
        terminal_run_btn = ft.IconButton(icon=ft.Icons.PLAY_ARROW_ROUNDED, tooltip="执行命令", icon_color=ft.Colors.ON_SURFACE_VARIANT, ink=True)
        terminal_run_btn.on_click = lambda e: self._run_terminal_command()
        self.terminal_input.on_submit = lambda e: self._run_terminal_command()
        self.terminal_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO)
        self.mcp_list = ft.ListView(expand=True, spacing=4, auto_scroll=True, scroll=ft.ScrollMode.AUTO)
        
        clear_terminal_btn = ft.TextButton("清空终端", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6), bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER), icon=ft.Icons.DELETE_OUTLINE_ROUNDED, ink=True)
        clear_terminal_btn.on_click = lambda e: self._clear_terminal()
        clear_mcp_btn = ft.TextButton("清空 MCP", style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=6), bgcolor=ft.Colors.ERROR_CONTAINER, color=ft.Colors.ON_ERROR_CONTAINER), icon=ft.Icons.DELETE_OUTLINE_ROUNDED, ink=True)
        clear_mcp_btn.on_click = lambda e: self._clear_mcp()
        
        terminal_tab = ft.Column(
            [
                ft.Row([self.terminal_input, terminal_run_btn], spacing=8),
                ft.Row([clear_terminal_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(self.terminal_list, expand=True, border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), left=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), right=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)), border_radius=12, padding=12, bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        mcp_tab = ft.Column(
            [
                ft.Row([clear_mcp_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(self.mcp_list, expand=True, border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), left=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), right=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)), border_radius=12, padding=12, bgcolor=ft.Colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self._right_terminal_tab = terminal_tab
        self._right_mcp_tab = mcp_tab
        self._right_tab_content = ft.Column(
            [
                terminal_tab,
                mcp_tab,
            ],
            expand=True,
        )
        self.right_tabs = ft.Tabs(
            content=self._right_tab_content,
            selected_index=0,
            on_change=lambda e: None,
            expand=True,
            tab_alignment=ft.TabAlignment.START,
        )
        return ft.Column(
            [
                self.right_tabs,
            ],
            expand=True,
            spacing=8,
        )
    
    def _append(self, role: str, text: str, retry: bool = False, retry_text: str = "", placeholder: bool = False):
        if hasattr(self, "_chat_placeholder") and self._chat_placeholder and self._chat_placeholder in self.chat_list.controls:
            self.chat_list.controls.remove(self._chat_placeholder)
        is_user = role == "你"
        align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        text_color = ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M")

        try:
            import markdown
            rendered = markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br"])
        except Exception:
            rendered = text

        is_error = not is_user and (text.startswith("Error:") or text.startswith("请求超时") or text.startswith("失败"))
        display_color = ft.Colors.ERROR if is_error else text_color

        if is_user:
            content_widget = ft.Column(
                [
                    self._markdown_to_ft(rendered),
                    ft.Text(timestamp, size=10, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.END),
                ],
                tight=True,
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.END,
            )
        else:
            content_widget = ft.Column(
                [
                    self._markdown_to_ft(rendered),
                    ft.Text(timestamp, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                tight=True,
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            )

        message_row = ft.Row(
            [content_widget],
            alignment=align,
            expand=True,
        )

        self.chat_list.controls.append(message_row)
        
        # Retry button for error messages
        if is_error and retry_text:
            retry_btn = ft.TextButton(
                "重试",
                icon=ft.Icons.REFRESH_ROUNDED,
                style=ft.ButtonStyle(color=ft.Colors.ERROR),
                on_click=lambda e, t=retry_text: self._send(t),
            )
            retry_row = ft.Row(
                [retry_btn],
                alignment=ft.MainAxisAlignment.START,
                expand=True,
            )
            self.chat_list.controls.append(retry_row)
        
        max_chat_items = 500
        if len(self.chat_list.controls) > max_chat_items:
            self.chat_list.controls = self.chat_list.controls[-max_chat_items:]
        self.chat_list.scroll_to(offset=-1, duration=200)
        self.chat_list.update()
        return message_row
    def _format_time(self) -> str:
        return datetime.now().strftime("%m-%d %H:%M")
    
    def _markdown_to_ft(self, text: str):
        html = markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br"])
        return ft.Markdown(
            value=html,
            selectable=True,
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            on_tap_link=lambda e: self.page.launch_url(e.data),
        )
    
    def _clear_chat(self):
        self.chat_list.controls.clear()
        if hasattr(self, "_chat_placeholder") and self._chat_placeholder:
            self.chat_list.controls.append(self._chat_placeholder)
        self.chat_list.update()
        self._update_input_count()
    
    def _show_message_menu(self, e, target, message_text: str):
        def _copy_msg(_):
            try:
                self.page.set_clipboard(message_text)
                self._set_status("已复制", ft.Colors.GREEN_400)
            except Exception:
                pass
        def _del_msg(_):
            try:
                self.chat_list.controls.remove(target)
                self.chat_list.update()
            except Exception:
                pass
        def _close(_):
            self.page.close_dialog()
        self.page.dialog = ft.AlertDialog(
            title=ft.Text("消息操作"),
            content=ft.Column([
                ft.TextButton("复制", on_click=_copy_msg, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))),
                ft.TextButton("删除", on_click=_del_msg, style=ft.ButtonStyle(color=ft.Colors.ERROR, shape=ft.RoundedRectangleBorder(radius=8))),
            ], tight=True, spacing=4),
            actions=[ft.TextButton("取消", on_click=_close, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))],
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.dialog.open = True
        self.page.update()
    
    def _append_terminal(self, text: str):
        self._terminal_lines.append(text)
        if len(self._terminal_lines) > 300:
            self._terminal_lines = self._terminal_lines[-300:]
        
        # Syntax highlighting
        color = ft.Colors.ON_SURFACE_VARIANT
        if 'error' in text.lower() or '失败' in text or '错误' in text:
            color = ft.Colors.ERROR
        elif 'warn' in text.lower() or '警告' in text:
            color = ft.Colors.AMBER_400
        elif 'success' in text.lower() or '成功' in text or 'saved' in text.lower():
            color = ft.Colors.GREEN_400
        elif 'info' in text.lower() or '信息' in text:
            color = ft.Colors.BLUE_400
        
    def _append_mcp(self, text: str):
        self._mcp_logs.append(text)
        if len(self._mcp_logs) > 200:
            self._mcp_logs = self._mcp_logs[-200:]
        self.mcp_list.controls.clear()
        for line in self._mcp_logs[-80:]:
            self.mcp_list.controls.append(
                ft.Text(line, size=12, color=ft.Colors.ON_SURFACE, selectable=True)
            )
        self.mcp_list.update()
    
    def _clear_terminal(self):
        self._terminal_lines = []
        self.terminal_list.controls.clear()
        self.terminal_list.update()
    
    def _clear_mcp(self):
        self._mcp_logs = []
        self.mcp_list.controls.clear()
        self.mcp_list.update()
    
    def _set_status(self, text: str, color=ft.Colors.GREEN_400):
        self.status_text.value = text
        self.status_text.color = color
        self.status_text.update()
        # Auto-clear status after 3 seconds
        try:
            import threading
            def _clear():
                import time
                time.sleep(3)
                if self.status_text.value == text:
                    self.status_text.value = 就绪
                    self.status_text.color = ft.Colors.GREEN_400
                    self.status_text.update()
            threading.Thread(target=_clear, daemon=True).start()
        except Exception:
            pass

    def _update_clock(self):
        try:
            now = datetime.now().strftime("%H:%M:%S")
            self._clock_text.value = now
            self._clock_text.update()
        except Exception:
            pass

    def _set_browser_status(self, connected: bool, text: str):
        self.browser_connected = connected
        self.browser_status_text.value = text
        self.browser_status_icon.color = ft.Colors.GREEN_400 if connected else ft.Colors.RED_400
        self.browser_status_icon.update()
        self.browser_status_text.update()
    
    def _save_config(self):
        prism_config.set("model.default", self.model_dropdown.value)
        prism_config.set("model.provider", self.provider_textfield.value)
        prism_config.set("model.base_url", (self.base_url_textfield.value or "").strip())
        prism_config.set("model.api_key", self.api_key_textfield.value)
        self._set_status("配置已保存")
        self._append_terminal("配置已保存")
        self.agent = create_agent()
    


    def _stop_send(self):
        self.input_field.disabled = False
        self.input_field.focus()
        self.input_field.update()
        self.send_btn.visible = True
        self.stop_btn.visible = False
        self.send_btn.update()
        self.stop_btn.update()
        self._set_status("已停止", ft.Colors.RED_400)

    def _browser_open(self):
        url = self.url_field.value.strip()
        if not url:
            self._set_status("请输入网址", ft.Colors.RED_400)
            return
        self._set_status("正在打开网页...", ft.Colors.AMBER_400)
        self._append_terminal(f"browser open {url}")
        result = open_page(url, headless=False)
        if result.get("success"):
            self._set_browser_status(True, f"已连接：{result.get('url', url)}")
            self._set_status(f"已打开：{result.get('url', url)}")
            self._append("浏览器", f"已打开：{result.get('url', url)}\n标题：{result.get('title', 'N/A')}")
            self._append_terminal(f"browser opened {result.get('url')}")
        else:
            self._set_browser_status(False, "打开失败")
            self._set_status(f"打开失败：{result.get('error')}", ft.Colors.RED_400)
            self._append("浏览器", f"打开失败：{result.get('error')}")
            self._append_terminal(f"browser error: {result.get('error')}")
    
    def _browser_snapshot(self):
        if not self.browser_connected:
            self._set_status("浏览器未连接", ft.Colors.RED_400)
            return
        self._set_status("正在读取页面...", ft.Colors.AMBER_400)
        self._append_terminal("browser snapshot ...")
        result = page_snapshot()
        if result.get("success"):
            content = result.get("content", "") or "(空)"
            self._set_status(f"页面快照：{result.get('title', 'N/A')}")
            self._append("页面快照", f"URL：{result.get('url')}\n标题：{result.get('title')}\n\n{content[:1200]}")
            self._append_terminal(f"browser snapshot: {result.get('title')}")
        else:
            self._set_browser_status(False, "快照失败")
            self._set_status(f"快照失败：{result.get('error')}", ft.Colors.RED_400)
            self._append("页面快照", f"失败：{result.get('error')}")
            self._append_terminal(f"browser snapshot error: {result.get('error')}")
    
    def _browser_close(self):
        self._append_terminal("browser close ...")
        result = close_browser()
        if result.get("success"):
            self._set_browser_status(False, "未连接")
            self._set_status("浏览器已关闭")
            self._append("浏览器", "浏览器已关闭")
            self._append_terminal("browser closed")
        else:
            self._set_browser_status(False, "关闭失败")
            self._set_status(f"关闭失败：{result.get('error')}", ft.Colors.RED_400)
            self._append("浏览器", f"关闭失败：{result.get('error')}")
            self._append_terminal(f"browser close error: {result.get('error')}")

    def _run_terminal_command(self):
        command = self.terminal_input.value.strip()
        if not command:
            return
        self._append_terminal(f">>> {command}")
        self.terminal_input.value = ""
        self.terminal_input.update()
        self._set_status("执行命令中...", ft.Colors.AMBER_400)
        try:
            from prism.tools.registry import registry
            result = registry.execute('terminal', command=command, timeout=180)
            output = result.get('output') or result.get('error') or '(无输出)'
            self._append_terminal(output)
            self._append_mcp(f"[terminal] {command[:80]}")
        except Exception as e:
            self._append_terminal(f"终端执行失败：{e}")
        self._set_status("就绪")

    def _refresh_mcp(self):
        self._append_terminal("mcp refresh ...")
        self.mcp_server_list.controls.clear()
        try:
            raw = prism_config.get("mcp.servers") or []
        except Exception:
            raw = []
        if not raw:
            self.mcp_server_list.controls.append(
                ft.Text("未配置 MCP 服务器", size=12, color=ft.Colors.ON_SURFACE)
            )
        else:
            for idx, server in enumerate(raw):
                name = server.get("name") or server.get("id") or f"server_{idx+1}"
                transport = server.get("transport", "unknown")
                status = "未启动"
                start_btn = ft.TextButton("启动", data=name)
                start_btn.on_click = lambda e, s=name, b=start_btn: self._toggle_mcp_server(s, b)
                log_btn = ft.TextButton("日志", data=name)
                log_btn.on_click = lambda e, s=name: self._show_mcp_log(s)
                tools_btn = ft.TextButton("工具", data=name)
                tools_btn.on_click = lambda e, s=name: self._show_mcp_tools(s)
                row = ft.Row(
                    [
                        ft.Text(name, size=12, expand=True),
                        ft.Text(transport, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(status, size=11, color=ft.Colors.ON_SURFACE),
                        start_btn,
                        tools_btn,
                        log_btn,
                    ]
                )
                self.mcp_server_list.controls.append(row)
        self.mcp_server_list.update()
        self._append_mcp(f"已刷新 MCP 服务器：{len(raw)} 个")

    def _toggle_mcp_server(self, name: str, button: ft.TextButton):
        self._append_terminal(f"mcp toggle {name}")
        try:
            from prism.mcp import mcp_client
            current = self._mcp_server_status.get(name, False)
            if current:
                mcp_client.close()
                self._mcp_server_status[name] = False
                state = "已停止"
                button.text = "启动"
            else:
                raw = prism_config.get("mcp.servers") or []
                server_cfg = next((s for s in raw if (s.get("name") or s.get("id")) == name), None)
                if server_cfg:
                    from prism.mcp import MCPServer
                    mcp_client.add_server(MCPServer(
                        name=name,
                        transport=server_cfg.get("transport", "stdio"),
                        command=server_cfg.get("command"),
                        url=server_cfg.get("url"),
                        args=server_cfg.get("args") or [],
                    ))
                    self._mcp_server_status[name] = True
                    state = "已启动"
                    button.text = "已启动"
                else:
                    state = "配置缺失"
                    button.text = "启动"
            self._append_mcp(f"[{name}] {state}")
            button.update()
        except Exception as e:
            self._append_mcp(f"[{name}] 切换失败：{e}")

    def _show_mcp_log(self, name: str):
        self._append_mcp(f"[{name}] 日志入口后续接入真实 MCP 客户端")
        self._append_terminal(f"mcp log {name}")

    def _show_mcp_tools(self, name: str):
        self._append_terminal(f"mcp tools {name}")
        try:
            from prism.mcp import mcp_client
            tools = mcp_client.list_tools(name)
            self.mcp_list.controls.clear()
            if not tools:
                self.mcp_list.controls.append(ft.Text("暂无工具", size=12, color=ft.Colors.ON_SURFACE))
            else:
                for tool in tools:
                    schema = tool.get("inputSchema") or {}
                    self.mcp_list.controls.append(
                        ft.Text(f"- {tool.get('name')}: {tool.get('description', '')}", size=11)
                    )
            self.mcp_list.update()
            self._append_mcp(f"[{name}] 工具数：{len(tools)}")
        except Exception as e:
            self._append_mcp(f"[{name}] 工具获取失败：{e}")

    def _refresh_skills(self):
        self._append_terminal("skills refresh ...")
        self.skill_list.controls.clear()
        try:
            from prism.skills import skills as skill_registry
            items = skill_registry.list_skills()
        except Exception as e:
            items = []
            self._append_terminal(f"skills load error: {e}")
        self._skill_list_cache = items
        if not items:
            self.skill_list.controls.append(
                ft.Text("暂无可用 Skills", size=12, color=ft.Colors.ON_SURFACE)
            )
        else:
            for skill in items:
                name = skill.get("name", "unknown")
                desc = skill.get("description", "")
                enabled = skill.get("enabled", True)
                triggers = skill.get("triggers", []) or []
                status = "启用" if enabled else "禁用"
                toggle = ft.TextButton("启用" if not enabled else "禁用", data=name)
                toggle.on_click = lambda e, s=name: self._toggle_skill(s)
                run_btn = ft.TextButton("运行", data=name)
                run_btn.on_click = lambda e, s=name: self._run_skill(s)
                trigger_text = ", ".join(triggers) if triggers else ""
                self.skill_list.controls.append(
                    ft.Row(
                        [
                            ft.Text(name, size=12, expand=True),
                            ft.Text(status, size=11, color=ft.Colors.ON_SURFACE),
                            toggle,
                            run_btn,
                        ]
                    )
                )
                if desc:
                    self.skill_list.controls.append(
                        ft.Text(desc, size=11, color=ft.Colors.ON_SURFACE)
                    )
                if trigger_text:
                    self.skill_list.controls.append(
                        ft.Text(f"触发词：{trigger_text}", size=10, color=ft.Colors.ON_SURFACE)
                    )
        self.skill_list.update()
        self._append_mcp(f"已刷新 Skills：{len(items)} 个")

    def _toggle_skill(self, name: str):
        self._append_terminal(f"skill toggle {name}")
        try:
            from prism.skills import skills as skill_registry
            skill = skill_registry.get(name)
            if skill:
                skill.enabled = not skill.enabled
                state = "启用" if skill.enabled else "禁用"
                self._append_mcp(f"[{name}] 已{state}")
            else:
                self._append_mcp(f"[{name}] 未找到")
        except Exception as e:
            self._append_mcp(f"[{name}] 切换失败：{e}")
        self._refresh_skills()

    def _run_skill(self, name: str):
        self._append_terminal(f"skill run {name}")
        try:
            from prism.skills import skills as skill_registry
            result = skill_registry.execute(name)
            self._append_mcp(f"[{name}] {result}")
        except Exception as e:
            self._append_mcp(f"[{name}] 运行失败：{e}")

    def _install_skill_from_ui(self):
        name = (self.skill_install_field.value or "").strip()
        if not name:
            self._set_status("请输入 Skill 名称或本地路径", ft.Colors.RED_400)
            return
        self._append_terminal(f"skill install {name}")
        try:
            from prism.skills import skills as skill_registry
            result = skill_registry.install_skill(name)
            if result.get("success"):
                self._append_mcp(f"[install] {result.get('message')}")
                self._set_status("Skill 安装成功")
            else:
                self._append_mcp(f"[install] 失败：{result.get('error')}")
                self._set_status("Skill 安装失败", ft.Colors.RED_400)
        except Exception as e:
            self._append_mcp(f"[install] 异常：{e}")
            self._set_status("Skill 安装异常", ft.Colors.RED_400)
        self.skill_install_field.value = ""
        self.skill_install_field.update()
        self._refresh_skills()

    def _save_session(self):
        name = (self.session_name_field.value or "").strip()
        if not name:
            self._set_status("请输入会话名称", ft.Colors.RED_400)
            return
        try:
            path = self.agent.save_session(name)
            self._append_terminal(f"session saved: {path}")
            self._set_status("会话已保存")
        except Exception as e:
            self._append_terminal(f"session save failed: {e}")
            self._set_status("会话保存失败", ft.Colors.RED_400)
        self.session_name_field.value = ""
        self.session_name_field.update()
        self._refresh_sessions()

    def _new_session(self):
        self._current_session_name = None
        self.chat_list.controls.clear()
        if hasattr(self, "_chat_placeholder") and self._chat_placeholder:
            self.chat_list.controls.append(self._chat_placeholder)
        self.chat_list.update()
        self.input_field.value = ""
        self.input_field.focus()
        self._update_input_count()
        self._set_status("新对话")
        self._append_terminal("new session")

    def _new_session(self):
        self._current_session_name = None
        self.chat_list.controls.clear()
        if hasattr(self, "_chat_placeholder") and self._chat_placeholder:
            self.chat_list.controls.append(self._chat_placeholder)
        self.chat_list.update()
        self.input_field.value = ""
        self.input_field.focus()
        self._update_input_count()
        self._set_status("新对话")
        self._append_terminal("new session")

    def _refresh_sessions(self):
        self.session_list.controls.clear()
        try:
            names = self.agent.list_sessions()
        except Exception:
            names = []
        # Sort: pinned first, then alphabetical
        pinned = self._settings.get("pinned_sessions", {}) or {}
        names = sorted(names, key=lambda n: (not pinned.get(n, False), n))
        # Sort: pinned first, then alphabetical
        pinned = self._settings.get("pinned_sessions", {}) or {}
        names = sorted(names, key=lambda n: (not pinned.get(n, False), n))
        if not names:
            self.session_list.controls.append(self._session_empty_text)
        else:
            for name in names:
                is_current = name == self._current_session_name
                # Pin button
                pin_btn = ft.IconButton(
                    icon=ft.Icons.PUSH_PIN_ROUNDED if self._settings.get("pinned_sessions", {}).get(name) else ft.Icons.PUSH_PIN_OUTLINE_ROUNDED,
                    tooltip="置顶" if self._settings.get("pinned_sessions", {}).get(name) else "取消置顶",
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    width=32,
                    height=32,
                )
                pin_btn.on_click = lambda e, n=name: self._toggle_pin_session(n)

                # Rename button
                rename_btn = ft.IconButton(icon=ft.Icons.EDIT_OUTLINE, tooltip="重命名", icon_color=ft.Colors.ON_SURFACE_VARIANT, width=32, height=32)
                rename_btn.on_click = lambda e, n=name: self._rename_session(n)

                load_btn = ft.Button(
                    name,
                    expand=True,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.PRIMARY_CONTAINER if is_current else None,
                        color=ft.Colors.ON_PRIMARY_CONTAINER if is_current else None,
                        shape=ft.RoundedRectangleBorder(radius=6),
                        padding=ft.Padding(10, 8, 10, 8),
                    ),
                )
                load_btn.on_click = lambda e, n=name: self._load_session(n)
                del_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="删除会话", icon_color=ft.Colors.ERROR, width=32, height=32)
                del_btn.on_click = lambda e, n=name: self._delete_session(n)
                self.session_list.controls.append(
                    ft.Row([pin_btn, load_btn, rename_btn, del_btn], spacing=4, tight=True)
                )
        self.session_list.update()

    def _delete_session(self, name: str):
        try:
            ok = self.agent.delete_session(name)
            if ok and name == self._current_session_name:
                self._current_session_name = None
            self._append_terminal(f"session delete {name}: {'ok' if ok else 'failed'}")
            self._set_status("会话已删除" if ok else "删除失败", ft.Colors.GREEN_400 if ok else ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"session delete error: {e}")
            self._set_status("删除异常", ft.Colors.RED_400)
        self._refresh_sessions()

    def _toggle_pin_session(self, name: str):
        pinned = self._settings.get("pinned_sessions", {}) or {}
        pinned[name] = not pinned.get(name, False)
        self._settings["pinned_sessions"] = pinned
        self._save_settings()
        self._refresh_sessions()

    def _rename_session(self, name: str):
        def on_submit(e):
            new_name = (rename_field.value or "").strip()
            if not new_name:
                self._set_status("名称不能为空", ft.Colors.RED_400)
                return
            if new_name != name:
                try:
                    ok = self.agent.rename_session(name, new_name)
                    if ok:
                        if self._current_session_name == name:
                            self._current_session_name = new_name
                        self._refresh_sessions()
                        self._set_status(f"已重命名为: {new_name}")
                    else:
                        self._set_status("重命名失败", ft.Colors.RED_400)
                except Exception as e:
                    self._set_status(f"重命名异常: {e}", ft.Colors.RED_400)
            dialog.open = False
            self.page.update()

        rename_field = ft.TextField(value=name, label="新会话名称", border_radius=8, autofocus=True)
        rename_field.on_submit = on_submit
        dialog = ft.AlertDialog(
            title=ft.Text("重命名会话"),
            content=rename_field,
            actions=[
                ft.TextButton("取消", on_click=lambda e: (setattr(dialog, "open", False), self.page.update())),
                ft.TextButton("确定", on_click=on_submit),
            ],
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    def _load_session(self, name: str):
        try:
            ok = self.agent.load_session(name)
            if ok:
                self._current_session_name = name
                self._append_terminal(f"session loaded: {name}")
                self._set_status("会话已加载")
                self.chat_list.controls.clear()
                for m in self.agent.messages:
                    if m.role == "system":
                        continue
                    role_label = "你" if m.role == "user" else ("PRISM" if m.role == "assistant" else m.role)
                    self._append(role_label, m.content or "")
                self.chat_list.update()
                self._refresh_sessions()
            else:
                self._append_terminal(f"session load failed: {name}")
                self._set_status("会话加载失败", ft.Colors.RED_400)
        except Exception as e:
            self._append_terminal(f"session load error: {e}")
            self._set_status("会话加载异常", ft.Colors.RED_400)


def main():
    def _app(page: ft.Page):
        PrismDesktop(page)
    ft.run(main=_app)


if __name__ == "__main__":
    main()
