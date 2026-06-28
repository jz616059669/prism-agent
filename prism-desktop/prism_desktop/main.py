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
        self.page.padding = 20
        self.page.window_width = 1320
        self.page.window_height = 800
        self.page.theme = ft.Theme(color_scheme_seed="blue")
        
        self._settings = {}
        
        self.status_text = ft.Text("就绪", size=11, color=ft.Colors.RED_400)
        self.browser_status_icon = ft.Icon(ft.Icons.LANGUAGE_ROUNDED, size=16, color=ft.Colors.RED_400)
        self.browser_status_text = ft.Text("未连接", size=11, color=ft.Colors.RED_400)
        
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
        self._maybe_show_setup_wizard()
        self._settings = self._load_settings()
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
            self.page.theme = ft.Theme(color_scheme_seed="blue")
        elif name == "Midnight":
            self.page.theme_mode = ft.ThemeMode.DARK
            self.page.theme = ft.Theme(color_scheme_seed="indigo")
        elif name == "Warm":
            self.page.theme_mode = ft.ThemeMode.LIGHT
            self.page.theme = ft.Theme(color_scheme_seed="orange")
        else:
            self.page.theme_mode = ft.ThemeMode.DARK
            self.page.theme = ft.Theme(color_scheme_seed="blue")
        self.page.update()
        self._append_terminal(f"theme -> {name}")
        self._save_settings()

    def _build_appbar(self) -> ft.AppBar:
        self.title_text = ft.Text("PRISM Agent", size=18, weight=ft.FontWeight.BOLD)
        self.theme_icon_btn = ft.IconButton(icon=ft.Icons.SETTINGS, tooltip="切换主题")
        self.theme_icon_btn.on_click = lambda e: self._cycle_theme()
        self.minimize_btn = ft.IconButton(icon=ft.Icons.MINIMIZE_ROUNDED, tooltip="最小化到托盘")
        self.minimize_btn.on_click = lambda e: self._minimize_to_tray()
        self.about_btn = ft.IconButton(icon=ft.Icons.INFO_ROUNDED, tooltip="关于")
        self.about_btn.on_click = lambda e: self._about(e)
        self.sidebar_toggle_btn = ft.IconButton(icon=ft.Icons.MENU_ROUNDED, tooltip="切换侧边栏")
        self.sidebar_toggle_btn.on_click = lambda e: self._toggle_sidebar()
        return ft.AppBar(
            title=self.title_text,
            actions=[
                self.sidebar_toggle_btn,
                self.theme_icon_btn,
                self.minimize_btn,
                self.about_btn,
            ],
        )

    def _toggle_sidebar(self):
        if not hasattr(self, "_sidebar_container"):
            return
        visible = self._sidebar_container.visible
        self._sidebar_container.visible = not visible
        width = 0 if visible else 280
        self._sidebar_container.width = width
        self._sidebar_container.update()
        self._settings["sidebar_collapsed"] = not visible
        self._save_settings()
        self.page.update()

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
            bgcolor=ft.Colors.SURFACE,
            border_radius=12,
        )

        save_btn = ft.Button("保存配置", icon=ft.Icons.SAVE_ROUNDED, width=260)
        save_btn.on_click = lambda e: self._save_config()

        self.url_field = ft.TextField(hint_text="输入网址...", width=260)
        browser_open_btn = ft.Button("打开网页", icon=ft.Icons.LANGUAGE_ROUNDED, width=260)
        browser_open_btn.on_click = lambda e: self._browser_open()
        browser_snapshot_btn = ft.Button("读取页面快照", icon=ft.Icons.ARTICLE_ROUNDED, width=260)
        browser_snapshot_btn.on_click = lambda e: self._browser_snapshot()
        browser_close_btn = ft.Button("关闭浏览器", icon=ft.Icons.CLOSE_ROUNDED, width=260)
        browser_close_btn.on_click = lambda e: self._browser_close()

        # MCP
        self.mcp_refresh_btn = ft.Button("刷新 MCP 服务器", icon=ft.Icons.REFRESH_ROUNDED, width=260)
        self.mcp_refresh_btn.on_click = lambda e: self._refresh_mcp()
        self.mcp_server_list = ft.Column(spacing=4, tight=True)

        # Skills
        self.skill_refresh_btn = ft.Button("刷新 Skills", icon=ft.Icons.REFRESH_ROUNDED, width=260)
        self.skill_refresh_btn.on_click = lambda e: self._refresh_skills()
        self.skill_install_field = ft.TextField(hint_text="安装 Skill 名称或本地路径", width=260)
        self.skill_install_btn = ft.Button("安装 Skill", icon=ft.Icons.DOWNLOAD_ROUNDED, width=260)
        self.skill_install_btn.on_click = lambda e: self._install_skill_from_ui()
        self.skill_list = ft.Column(spacing=4, tight=True)

        # 会话
        self.session_name_field = ft.TextField(hint_text="会话名称", width=200)
        self.session_save_btn = ft.Button("保存会话", icon=ft.Icons.BOOKMARK_ROUNDED, width=120)
        self.session_save_btn.on_click = lambda e: self._save_session()
        self.session_list = ft.Column(spacing=4, tight=True)
        self._session_empty_text = ft.Text("暂无保存的会话", size=11, color=ft.Colors.ON_SURFACE)

        sidebar_content = self._sidebar_container.content
        sidebar_content.controls.extend([
            ft.Text("模型配置", size=12, weight=ft.FontWeight.BOLD),
            self.model_dropdown,
            ft.Container(height=6),
            self.provider_textfield,
            ft.Container(height=6),
            self.base_url_textfield,
            ft.Container(height=6),
            self.api_key_textfield,
            ft.Container(height=6),
            save_btn,
            ft.Container(height=16),
            ft.Text("浏览器控制", size=12, weight=ft.FontWeight.BOLD),
            self.url_field,
            browser_open_btn,
            browser_snapshot_btn,
            browser_close_btn,
            ft.Container(height=16),
            ft.Text("MCP 控制", size=12, weight=ft.FontWeight.BOLD),
            self.mcp_refresh_btn,
            ft.Container(height=6),
            ft.Text("已配置服务器", size=11, color=ft.Colors.ON_SURFACE),
            self.mcp_server_list,
            ft.Container(height=16),
            ft.Text("Skills", size=12, weight=ft.FontWeight.BOLD),
            self.skill_refresh_btn,
            self.skill_install_field,
            self.skill_install_btn,
            ft.Container(height=6),
            ft.Text("可用 Skills", size=11, color=ft.Colors.ON_SURFACE),
            self.skill_list,
            ft.Container(height=16),
            ft.Text("会话", size=12, weight=ft.FontWeight.BOLD),
            ft.Row([self.session_name_field, self.session_save_btn], spacing=8),
            ft.Container(height=6),
            ft.Text("已保存会话", size=11, color=ft.Colors.ON_SURFACE),
            self.session_list,
            ft.Container(height=16),
            ft.Text("状态", size=12, weight=ft.FontWeight.BOLD),
            ft.Row([self.browser_status_icon, self.browser_status_text], spacing=8),
            self.status_text,
        ])
        return self._sidebar_container

    def _build_chat(self) -> ft.Column:
        self.chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
        self.input_field = ft.TextField(
            hint_text="输入消息...",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=6,
            shift_enter=True,
        )
        self.input_count = ft.Text("0 字", size=11, color=ft.Colors.ON_SURFACE)
        self.input_field.on_change = lambda e: self._on_input_change()
        self.send_btn = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, tooltip="发送")
        self.send_btn.on_click = lambda e: self._send()
        self.stop_btn = ft.IconButton(icon=ft.Icons.STOP_ROUNDED, tooltip="停止生成", visible=False)
        self.stop_btn.on_click = lambda e: self._stop_send()
        self.input_field.on_submit = lambda e: self._send()
        clear_chat_btn = ft.TextButton("清屏")
        clear_chat_btn.on_click = lambda e: self._clear_chat()
        
        return ft.Column(
            [
                ft.Text("对话", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(height=8),
                ft.Container(self.chat_list, expand=True, border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), left=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), right=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)), border_radius=12, padding=12),
                ft.Divider(height=8),
                ft.Row([self.input_field, self.send_btn, self.stop_btn], spacing=8),
                ft.Row([clear_chat_btn, self.input_count], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
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
        )
        terminal_run_btn = ft.IconButton(icon=ft.Icons.PLAY_ARROW_ROUNDED, tooltip="执行命令")
        terminal_run_btn.on_click = lambda e: self._run_terminal_command()
        self.terminal_input.on_submit = lambda e: self._run_terminal_command()
        self.terminal_list = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        self.mcp_list = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        
        clear_terminal_btn = ft.TextButton("清空终端")
        clear_terminal_btn.on_click = lambda e: self._clear_terminal()
        clear_mcp_btn = ft.TextButton("清空 MCP")
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
            length=400,
            selected_index=0,
            on_change=lambda e: None,
            expand=True,
        )
        return ft.Column(
            [
                ft.Text("终端 / MCP", size=14, weight=ft.FontWeight.BOLD),
                self.right_tabs,
            ],
            expand=True,
            spacing=8,
        )
    
    def _append(self, role: str, text: str, retry: bool = False, retry_text: str = "", placeholder: bool = False):
        is_user = role == "你"
        align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        bg = ft.Colors.PRIMARY_CONTAINER if is_user else ft.Colors.SURFACE
        text_color = ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE
        avatar = ft.Icon(ft.Icons.PERSON_ROUNDED if is_user else ft.Icons.SMART_TOY_ROUNDED, size=28, color=ft.Colors.ON_SURFACE)

        def _copy(_):
            try:
                self.page.set_clipboard(text)
                self._set_status("已复制", ft.Colors.GREEN_400)
            except Exception:
                pass

        def _copy_raw(_):
            try:
                self.page.set_clipboard(text)
                self._set_status("已复制原文", ft.Colors.GREEN_400)
            except Exception:
                pass

        def _delete(_):
            try:
                self.chat_list.controls.remove(container_wrapper)
                self.chat_list.update()
                self._append_terminal("message deleted")
            except Exception:
                pass

        def _on_right_click(e):
            try:
                self._show_message_menu(e, container_wrapper, text)
            except Exception:
                pass

        try:
            import markdown
            rendered = markdown.markdown(text, extensions=["fenced_code", "tables"])
        except Exception:
            rendered = text

        actions = [
            ft.Text(self._format_time(), size=9, color=ft.Colors.ON_SURFACE),
            ft.TextButton("复制渲染", on_click=_copy),
            ft.TextButton("复制原文", on_click=_copy_raw),
            ft.TextButton("删除", on_click=_delete),
        ]
        if retry and retry_text:
            def _retry(_):
                self.input_field.value = retry_text
                self.input_field.disabled = False
                self.input_field.focus()
                self.input_field.update()
                self._send()
            actions.insert(2, ft.TextButton("重发", on_click=_retry))

        if placeholder:
            actions = [ft.Text(self._format_time(), size=9, color=ft.Colors.ON_SURFACE)]

        import re
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)
        code_copy_buttons = []
        for idx, block in enumerate(code_blocks):
            def _copy_code(b=block, index=idx):
                def handler(_):
                    try:
                        self.page.set_clipboard(b.strip())
                        self._set_status(f"代码块 {index+1} 已复制", ft.Colors.GREEN_400)
                    except Exception:
                        pass
                return handler
            code_copy_buttons.append(
                ft.TextButton(f"复制代码块 {idx+1}", on_click=_copy_code(), style=ft.ButtonStyle(padding=4))
            )

        action_row = ft.Row(actions, spacing=8)
        if code_copy_buttons:
            action_row.controls.extend(code_copy_buttons)

        content = ft.Column(
            [
                ft.Text(role, size=11, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.BOLD),
                self._markdown_to_ft(rendered),
                action_row,
            ],
            tight=True,
        )

        container_wrapper = ft.Container(
            content=content,
            bgcolor=bg,
            padding=10,
            border_radius=16,
            expand=True,
            on_long_press=_on_right_click,
        )

        spacer = ft.Container(width=8)
        if is_user:
            row_controls = [container_wrapper, spacer, avatar]
        else:
            row_controls = [avatar, spacer, container_wrapper]
        self.chat_list.controls.append(
            ft.Row(
                row_controls,
                alignment=align,
            )
        )
        # 防止聊天列表无限增长
        max_chat_items = 200
        if len(self.chat_list.controls) > max_chat_items:
            self.chat_list.controls = self.chat_list.controls[-max_chat_items:]
        self.chat_list.scroll_to(offset=-1, duration=150)
        self.chat_list.update()
        return container_wrapper
    
    def _build_appbar(self) -> ft.AppBar:
        self.title_text = ft.Text("PRISM Agent", size=18, weight=ft.FontWeight.BOLD)
        self.theme_icon_btn = ft.IconButton(icon=ft.Icons.SETTINGS, tooltip="切换主题")
        self.theme_icon_btn.on_click = lambda e: self._cycle_theme()
        self.minimize_btn = ft.IconButton(icon=ft.Icons.MINIMIZE_ROUNDED, tooltip="最小化到托盘")
        self.minimize_btn.on_click = lambda e: self._minimize_to_tray()
        self.about_btn = ft.IconButton(icon=ft.Icons.INFO_ROUNDED, tooltip="关于")
        self.about_btn.on_click = lambda e: self._about(e)
        self.sidebar_toggle_btn = ft.IconButton(icon=ft.Icons.MENU_ROUNDED, tooltip="切换侧边栏")
        self.sidebar_toggle_btn.on_click = lambda e: self._toggle_sidebar()
        return ft.AppBar(
            title=self.title_text,
            actions=[
                self.sidebar_toggle_btn,
                self.theme_icon_btn,
                self.minimize_btn,
                self.about_btn,
            ],
        )

    def _toggle_sidebar(self):
        if not hasattr(self, "_sidebar_container"):
            return
        visible = self._sidebar_container.visible
        self._sidebar_container.visible = not visible
        width = 0 if visible else 280
        self._sidebar_container.width = width
        self._sidebar_container.update()
        self._settings["sidebar_collapsed"] = not visible
        self._save_settings()
        self.page.update()

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
            bgcolor=ft.Colors.SURFACE,
            border_radius=12,
        )

        save_btn = ft.Button("保存配置", icon=ft.Icons.SAVE_ROUNDED, width=260)
        save_btn.on_click = lambda e: self._save_config()

        self.url_field = ft.TextField(hint_text="输入网址...", width=260)
        browser_open_btn = ft.Button("打开网页", icon=ft.Icons.LANGUAGE_ROUNDED, width=260)
        browser_open_btn.on_click = lambda e: self._browser_open()
        browser_snapshot_btn = ft.Button("读取页面快照", icon=ft.Icons.ARTICLE_ROUNDED, width=260)
        browser_snapshot_btn.on_click = lambda e: self._browser_snapshot()
        browser_close_btn = ft.Button("关闭浏览器", icon=ft.Icons.CLOSE_ROUNDED, width=260)
        browser_close_btn.on_click = lambda e: self._browser_close()

        # MCP
        self.mcp_refresh_btn = ft.Button("刷新 MCP 服务器", icon=ft.Icons.REFRESH_ROUNDED, width=260)
        self.mcp_refresh_btn.on_click = lambda e: self._refresh_mcp()
        self.mcp_server_list = ft.Column(spacing=4, tight=True)

        # Skills
        self.skill_refresh_btn = ft.Button("刷新 Skills", icon=ft.Icons.REFRESH_ROUNDED, width=260)
        self.skill_refresh_btn.on_click = lambda e: self._refresh_skills()
        self.skill_install_field = ft.TextField(hint_text="安装 Skill 名称或本地路径", width=260)
        self.skill_install_btn = ft.Button("安装 Skill", icon=ft.Icons.DOWNLOAD_ROUNDED, width=260)
        self.skill_install_btn.on_click = lambda e: self._install_skill_from_ui()
        self.skill_list = ft.Column(spacing=4, tight=True)

        # 会话
        self.session_name_field = ft.TextField(hint_text="会话名称", width=200)
        self.session_save_btn = ft.Button("保存会话", icon=ft.Icons.BOOKMARK_ROUNDED, width=120)
        self.session_save_btn.on_click = lambda e: self._save_session()
        self.session_list = ft.Column(spacing=4, tight=True)
        self._session_empty_text = ft.Text("暂无保存的会话", size=11, color=ft.Colors.ON_SURFACE)

        sidebar_content = self._sidebar_container.content
        sidebar_content.controls.extend([
            ft.Text("模型配置", size=12, weight=ft.FontWeight.BOLD),
            self.model_dropdown,
            ft.Container(height=6),
            self.provider_textfield,
            ft.Container(height=6),
            self.base_url_textfield,
            ft.Container(height=6),
            self.api_key_textfield,
            ft.Container(height=6),
            save_btn,
            ft.Container(height=16),
            ft.Text("浏览器控制", size=12, weight=ft.FontWeight.BOLD),
            self.url_field,
            browser_open_btn,
            browser_snapshot_btn,
            browser_close_btn,
            ft.Container(height=16),
            ft.Text("MCP 控制", size=12, weight=ft.FontWeight.BOLD),
            self.mcp_refresh_btn,
            ft.Container(height=6),
            ft.Text("已配置服务器", size=11, color=ft.Colors.ON_SURFACE),
            self.mcp_server_list,
            ft.Container(height=16),
            ft.Text("Skills", size=12, weight=ft.FontWeight.BOLD),
            self.skill_refresh_btn,
            self.skill_install_field,
            self.skill_install_btn,
            ft.Container(height=6),
            ft.Text("可用 Skills", size=11, color=ft.Colors.ON_SURFACE),
            self.skill_list,
            ft.Container(height=16),
            ft.Text("会话", size=12, weight=ft.FontWeight.BOLD),
            ft.Row([self.session_name_field, self.session_save_btn], spacing=8),
            ft.Container(height=6),
            ft.Text("已保存会话", size=11, color=ft.Colors.ON_SURFACE),
            self.session_list,
            ft.Container(height=16),
            ft.Text("状态", size=12, weight=ft.FontWeight.BOLD),
            ft.Row([self.browser_status_icon, self.browser_status_text], spacing=8),
            self.status_text,
        ])
        return self._sidebar_container

    def _build_chat(self) -> ft.Column:
        self.chat_list = ft.ListView(expand=True, spacing=10, auto_scroll=True)
        self.input_field = ft.TextField(
            hint_text="输入消息...",
            expand=True,
            multiline=True,
            min_lines=1,
            max_lines=6,
            shift_enter=True,
        )
        self.input_count = ft.Text("0 字", size=11, color=ft.Colors.ON_SURFACE)
        self.input_field.on_change = lambda e: self._on_input_change()
        self.send_btn = ft.IconButton(icon=ft.Icons.SEND_ROUNDED, tooltip="发送")
        self.send_btn.on_click = lambda e: self._send()
        self.stop_btn = ft.IconButton(icon=ft.Icons.STOP_ROUNDED, tooltip="停止生成", visible=False)
        self.stop_btn.on_click = lambda e: self._stop_send()
        self.input_field.on_submit = lambda e: self._send()
        clear_chat_btn = ft.TextButton("清屏")
        clear_chat_btn.on_click = lambda e: self._clear_chat()
        
        return ft.Column(
            [
                ft.Text("对话", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(height=8),
                ft.Container(self.chat_list, expand=True, border=ft.Border(top=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), bottom=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), left=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT), right=ft.border.BorderSide(1, ft.Colors.OUTLINE_VARIANT)), border_radius=12, padding=12),
                ft.Divider(height=8),
                ft.Row([self.input_field, self.send_btn, self.stop_btn], spacing=8),
                ft.Row([clear_chat_btn, self.input_count], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
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
        )
        terminal_run_btn = ft.IconButton(icon=ft.Icons.PLAY_ARROW_ROUNDED, tooltip="执行命令")
        terminal_run_btn.on_click = lambda e: self._run_terminal_command()
        self.terminal_input.on_submit = lambda e: self._run_terminal_command()
        self.terminal_list = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        self.mcp_list = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        
        clear_terminal_btn = ft.TextButton("清空终端")
        clear_terminal_btn.on_click = lambda e: self._clear_terminal()
        clear_mcp_btn = ft.TextButton("清空 MCP")
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
            length=400,
            selected_index=0,
            on_change=lambda e: None,
            expand=True,
        )
        return ft.Column(
            [
                ft.Text("终端 / MCP", size=14, weight=ft.FontWeight.BOLD),
                self.right_tabs,
            ],
            expand=True,
            spacing=8,
        )
    
    def _append(self, role: str, text: str, retry: bool = False, retry_text: str = "", placeholder: bool = False):
        is_user = role == "你"
        align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        bg = ft.Colors.PRIMARY_CONTAINER if is_user else ft.Colors.SURFACE
        text_color = ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE
        avatar = ft.Icon(ft.Icons.PERSON_ROUNDED if is_user else ft.Icons.SMART_TOY_ROUNDED, size=28, color=ft.Colors.ON_SURFACE)

        def _copy(_):
            try:
                self.page.set_clipboard(text)
                self._set_status("已复制", ft.Colors.GREEN_400)
            except Exception:
                pass

        def _copy_raw(_):
            try:
                self.page.set_clipboard(text)
                self._set_status("已复制原文", ft.Colors.GREEN_400)
            except Exception:
                pass

        def _delete(_):
            try:
                self.chat_list.controls.remove(container_wrapper)
                self.chat_list.update()
                self._append_terminal("message deleted")
            except Exception:
                pass

        def _on_right_click(e):
            try:
                self._show_message_menu(e, container_wrapper, text)
            except Exception:
                pass

        try:
            import markdown
            rendered = markdown.markdown(text, extensions=["fenced_code", "tables"])
        except Exception:
            rendered = text

        actions = [
            ft.Text(self._format_time(), size=9, color=ft.Colors.ON_SURFACE),
            ft.TextButton("复制渲染", on_click=_copy),
            ft.TextButton("复制原文", on_click=_copy_raw),
            ft.TextButton("删除", on_click=_delete),
        ]
        if retry and retry_text:
            def _retry(_):
                self.input_field.value = retry_text
                self.input_field.disabled = False
                self.input_field.focus()
                self.input_field.update()
                self._send()
            actions.insert(2, ft.TextButton("重发", on_click=_retry))

        if placeholder:
            actions = [ft.Text(self._format_time(), size=9, color=ft.Colors.ON_SURFACE)]

        import re
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)
        code_copy_buttons = []
        for idx, block in enumerate(code_blocks):
            def _copy_code(b=block, index=idx):
                def handler(_):
                    try:
                        self.page.set_clipboard(b.strip())
                        self._set_status(f"代码块 {index+1} 已复制", ft.Colors.GREEN_400)
                    except Exception:
                        pass
                return handler
            code_copy_buttons.append(
                ft.TextButton(f"复制代码块 {idx+1}", on_click=_copy_code(), style=ft.ButtonStyle(padding=4))
            )

        action_row = ft.Row(actions, spacing=8)
        if code_copy_buttons:
            action_row.controls.extend(code_copy_buttons)

        content = ft.Column(
            [
                ft.Text(role, size=11, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.BOLD),
                self._markdown_to_ft(rendered),
                action_row,
            ],
            tight=True,
        )

        container_wrapper = ft.Container(
            content=content,
            bgcolor=bg,
            padding=10,
            border_radius=16,
            expand=True,
            on_long_press=_on_right_click,
        )

        spacer = ft.Container(width=8)
        if is_user:
            row_controls = [container_wrapper, spacer, avatar]
        else:
            row_controls = [avatar, spacer, container_wrapper]
        self.chat_list.controls.append(
            ft.Row(
                row_controls,
                alignment=align,
            )
        )
        # 防止聊天列表无限增长
        max_chat_items = 200
        if len(self.chat_list.controls) > max_chat_items:
            self.chat_list.controls = self.chat_list.controls[-max_chat_items:]
        self.chat_list.scroll_to(offset=-1, duration=150)
        self.chat_list.update()
        return container_wrapper
    
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
        self.chat_list.update()
    
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
                ft.TextButton("复制", on_click=_copy_msg),
                ft.TextButton("删除", on_click=_del_msg),
            ], tight=True),
            actions=[ft.TextButton("取消", on_click=_close)],
        )
        self.page.dialog.open = True
        self.page.update()
    
    def _append_terminal(self, text: str):
        self._terminal_lines.append(text)
        if len(self._terminal_lines) > 300:
            self._terminal_lines = self._terminal_lines[-300:]
        self.terminal_list.controls.append(
            ft.Text(text, size=12, color=ft.Colors.ON_SURFACE, selectable=True)
        )
        if len(self.terminal_list.controls) > 80:
            self.terminal_list.controls = self.terminal_list.controls[-80:]
        self.terminal_list.update()

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

    def _refresh_sessions(self):
        self.session_list.controls.clear()
        try:
            names = self.agent.list_sessions()
        except Exception:
            names = []
        if not names:
            self.session_list.controls.append(self._session_empty_text)
        else:
            for name in names:
                is_current = name == self._current_session_name
                load_btn = ft.Button(
                    name,
                    width=200,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.PRIMARY_CONTAINER if is_current else None,
                        color=ft.Colors.ON_PRIMARY_CONTAINER if is_current else None,
                    ),
                )
                load_btn.on_click = lambda e, n=name: self._load_session(n)
                del_btn = ft.IconButton(icon=ft.Icons.DELETE_OUTLINE, tooltip="删除会话")
                del_btn.on_click = lambda e, n=name: self._delete_session(n)
                self.session_list.controls.append(
                    ft.Row([load_btn, del_btn], spacing=6)
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
