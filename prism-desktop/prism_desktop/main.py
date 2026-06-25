"""
PRISM Agent - 桌面客户端
基于 Flet 实现，比 Codex CLI 更现代
已连通真实 Agent 后端 + 浏览器控制 + 终端输出 + MCP 控制
"""

import sys
from pathlib import Path
import json
import flet as ft
from typing import Optional

# 让桌面端可直接导入上层 prism 包，无需额外安装
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.config import config as prism_config
from prism.agent import create_agent
from prism.tools.browser_bridge import open_page, page_snapshot, close_browser


class PrismDesktop:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "PRISM Agent"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 20
        self.page.window_width = 1320
        self.page.window_height = 800
        self.page.theme = ft.Theme(color_scheme_seed="blue")
        
        # 持久化设置
        self._settings_path = Path.home() / ".prism" / "desktop_settings.json"
        self._settings = self._load_settings()
        
        self.messages = []
        self.agent = create_agent()
        self.browser_connected = False
        self._terminal_lines = ["PRISM Desktop 已启动"]
        self._mcp_logs = []
        self._skill_list_cache = []
        self._mcp_server_status = {}
        self._build_ui()
        self._apply_settings()
        self._bind_context_menu()
        self._bind_tray()

    def _load_settings(self) -> dict:
        if self._settings_path.exists():
            try:
                import json
                return json.loads(self._settings_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_settings(self) -> None:
        try:
            self._settings_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "window_width": int(self.page.window_width or 1320),
                "window_height": int(self.page.window_height or 800),
                "theme_mode": self.page.theme_mode.value if hasattr(self.page.theme_mode, "value") else str(self.page.theme_mode),
            }
            self._settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _apply_settings(self) -> None:
        try:
            width = self._settings.get("window_width")
            height = self._settings.get("window_height")
            if isinstance(width, int):
                self.page.window_width = width
            if isinstance(height, int):
                self.page.window_height = height
        except Exception:
            pass

    def _bind_context_menu(self) -> None:
        self.page.on_resized = lambda e: self._save_settings()
        self.page.on_window_event = lambda e: self._save_settings()

    def _bind_tray(self) -> None:
        try:
            self.page.window.prevent_close = True
            self.page.on_window_event = lambda e: (
                self._save_settings() if getattr(e, "data", None) != "close" else None
            )
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

    def _open_config_dir(self, e):
        config_dir = Path.home() / ".prism"
        config_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(config_dir))
        self._append_terminal(f"open config dir: {config_dir}")

    def _open_terminal_here(self, e):
        os.system('start cmd')
        self._append_terminal("open terminal")

    def _about(self, e):
        self.page.dialog = ft.AlertDialog(
            title=ft.Text("PRISM Agent"),
            content=ft.Text("版本：0.2.1\n统一 AI Agent CLI + 桌面客户端"),
            actions=[ft.TextButton("关闭", on_click=lambda e: self.page.close_dialog())],
        )
        self.page.dialog.open = True
        self.page.update()
        self._append_terminal("about dialog opened")
    
    def _build_appbar(self) -> ft.AppBar:
        self.title_text = ft.Text("PRISM Agent", size=18, weight=ft.FontWeight.BOLD)
        self.theme_icon_btn = ft.IconButton(icon=ft.icons.BRIGHTNESS_4_ROUNDED, tooltip="切换主题")
        self.theme_icon_btn.on_click = lambda e: self._cycle_theme()
        self.minimize_btn = ft.IconButton(icon=ft.icons.MINIMIZE_ROUNDED, tooltip="最小化到托盘")
        self.minimize_btn.on_click = lambda e: self._minimize_to_tray()
        return ft.AppBar(
            title=self.title_text,
            actions=[
                self.theme_icon_btn,
                self.minimize_btn,
            ],
        )

    def _cycle_theme(self):
        current = desktop_settings.get("theme", "Dark")
        themes = ["Dark", "Light", "Midnight", "Warm"]
        idx = themes.index(current) if current in themes else 0
        next_theme = themes[(idx + 1) % len(themes)]
        desktop_settings["theme"] = next_theme
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
        self.page.add(
            ft.Row(
                [
                    self._build_sidebar(),
                    ft.VerticalDivider(width=1),
                    self._build_chat(),
                    ft.VerticalDivider(width=1),
                    self._build_right_panel(),
                ],
                expand=True,
                spacing=0,
            )
        )
    
    def _build_sidebar(self) -> ft.Container:
        self.model_dropdown = ft.Dropdown(
            label="模型",
            value=prism_config.get("model.default", "step-3.7-flash"),
            options=[
                ft.dropdown.Option("step-3.7-flash"),
                ft.dropdown.Option("gpt-4o"),
                ft.dropdown.Option("gpt-4o-mini"),
            ],
            width=260,
        )
        self.provider_textfield = ft.TextField(
            label="提供商",
            value=prism_config.get("model.provider", "stepfun"),
            password=True,
            can_reveal_password=True,
            width=260,
        )
        self.api_key_textfield = ft.TextField(
            label="API Key",
            value=prism_config.get("model.api_key", ""),
            password=True,
            can_reveal_password=True,
            width=260,
        )
        self.status_text = ft.Text("就绪", size=12, color=ft.colors.GREEN_400)
        self.browser_status_icon = ft.Icon(ft.icons.CIRCLE, size=10, color=ft.colors.OUTLINE)
        self.browser_status_text = ft.Text("浏览器未连接", size=12, color=ft.colors.ON_SURFACE_VARIANT)
        
        self.theme_dropdown = ft.Dropdown(
            label="主题",
            value=desktop_settings.get("theme", "Dark"),
            width=260,
            options=[
                ft.dropdown.Option("Dark"),
                ft.dropdown.Option("Light"),
                ft.dropdown.Option("Midnight"),
                ft.dropdown.Option("Warm"),
            ],
        )
        self.theme_dropdown.on_change = lambda e: self._apply_theme(e.data)
        
        self.open_config_btn = ft.ElevatedButton("打开配置目录", width=260)
        self.open_config_btn.on_click = lambda e: self._open_config_dir(e)
        
        self.open_terminal_btn = ft.ElevatedButton("打开终端", width=260)
        self.open_terminal_btn.on_click = lambda e: self._open_terminal_here(e)
        
        self.about_btn = ft.ElevatedButton("关于", width=260)
        self.about_btn.on_click = lambda e: self._about(e)
        
        save_btn = ft.ElevatedButton("保存配置", width=260)
        save_btn.on_click = lambda e: self._save_config()
        
        self.url_field = ft.TextField(
            hint_text="输入网址...",
            value="https://example.com",
            width=260,
        )
        browser_open_btn = ft.ElevatedButton("打开网页", width=260)
        browser_open_btn.on_click = lambda e: self._browser_open()
        
        browser_snapshot_btn = ft.ElevatedButton("读取页面快照", width=260)
        browser_snapshot_btn.on_click = lambda e: self._browser_snapshot()
        
        browser_close_btn = ft.ElevatedButton("关闭浏览器", width=260)
        browser_close_btn.on_click = lambda e: self._browser_close()
        
        # MCP
        self.mcp_refresh_btn = ft.ElevatedButton("刷新 MCP 服务器", width=260)
        self.mcp_refresh_btn.on_click = lambda e: self._refresh_mcp()
        self.mcp_server_list = ft.Column(spacing=4, tight=True)
        
        # Skills
        self.skill_refresh_btn = ft.ElevatedButton("刷新 Skills", width=260)
        self.skill_refresh_btn.on_click = lambda e: self._refresh_skills()
        self.skill_install_field = ft.TextField(hint_text="安装 Skill 名称或本地路径", width=260)
        self.skill_install_btn = ft.ElevatedButton("安装 Skill", width=260)
        self.skill_install_btn.on_click = lambda e: self._install_skill_from_ui()
        self.skill_list = ft.Column(spacing=4, tight=True)
        
        # 会话
        self.session_name_field = ft.TextField(hint_text="会话名称", width=200)
        self.session_save_btn = ft.ElevatedButton("保存会话", width=120)
        self.session_save_btn.on_click = lambda e: self._save_session()
        self.session_list = ft.Column(spacing=4, tight=True)
        
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("PRISM", size=20, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=12, color=ft.colors.TRANSPARENT),
                    self.model_dropdown,
                    ft.Container(height=6),
                    self.provider_textfield,
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
                    ft.Text("已配置服务器", size=11, color=ft.colors.ON_SURFACE_VARIANT),
                    self.mcp_server_list,
                    ft.Container(height=16),
                    ft.Text("Skills", size=12, weight=ft.FontWeight.BOLD),
                    self.skill_refresh_btn,
                    self.skill_install_field,
                    self.skill_install_btn,
                    ft.Container(height=6),
                    ft.Text("可用 Skills", size=11, color=ft.colors.ON_SURFACE_VARIANT),
                    self.skill_list,
                    ft.Container(height=16),
                    ft.Text("会话", size=12, weight=ft.FontWeight.BOLD),
                    ft.Row([self.session_name_field, self.session_save_btn], spacing=8),
                    ft.Container(height=6),
                    ft.Text("已保存会话", size=11, color=ft.colors.ON_SURFACE_VARIANT),
                    self.session_list,
                    ft.Container(height=16),
                    ft.Text("状态", size=12, weight=ft.FontWeight.BOLD),
                    ft.Row([self.browser_status_icon, self.browser_status_text], spacing=8),
                    self.status_text,
                ],
                tight=True,
                spacing=6,
                scroll=ft.ScrollMode.AUTO,
            ),
            width=280,
            padding=16,
            bgcolor=ft.colors.SURFACE_VARIANT,
            border_radius=12,
        )
    
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
        send_btn = ft.IconButton(icon=ft.icons.SEND_ROUNDED, tooltip="发送")
        send_btn.on_click = lambda e: self._send()
        self.input_field.on_submit = lambda e: self._send()
        clear_chat_btn = ft.TextButton("清屏")
        clear_chat_btn.on_click = lambda e: self._clear_chat()
        
        return ft.Column(
            [
                ft.Text("对话", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(height=8),
                ft.Container(self.chat_list, expand=True, border=ft.border.all(1, ft.colors.OUTLINE_VARIANT), border_radius=12, padding=12),
                ft.Divider(height=8),
                ft.Row([self.input_field, send_btn], spacing=8),
                ft.Row([clear_chat_btn], alignment=ft.MainAxisAlignment.END),
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
        terminal_run_btn = ft.IconButton(icon=ft.icons.PLAY_ARROW_ROUNDED, tooltip="执行命令")
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
                ft.Container(self.terminal_list, expand=True, border=ft.border.all(1, ft.colors.OUTLINE_VARIANT), border_radius=12, padding=12, bgcolor=ft.colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        mcp_tab = ft.Column(
            [
                ft.Row([clear_mcp_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(self.mcp_list, expand=True, border=ft.border.all(1, ft.colors.OUTLINE_VARIANT), border_radius=12, padding=12, bgcolor=ft.colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
        self.right_tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            tabs=[
                ft.Tab(text="终端", content=terminal_tab),
                ft.Tab(text="MCP", content=mcp_tab),
            ],
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
    
    def _append(self, role: str, text: str):
        is_user = role == "你"
        align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        color = ft.colors.PRIMARY_CONTAINER if is_user else ft.colors.SURFACE_VARIANT
        text_color = ft.colors.ON_PRIMARY_CONTAINER if is_user else ft.colors.ON_SURFACE
        
        def _copy(_):
            try:
                self.page.set_clipboard(text)
                self._set_status("已复制", ft.colors.GREEN_400)
            except Exception:
                pass
        
        try:
            import markdown
            rendered = markdown.markdown(text, extensions=["fenced_code", "tables"])
        except Exception:
            rendered = text
        
        content = ft.Column(
            [
                ft.Text(role, size=11, color=ft.colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.BOLD),
                ft.Text(rendered, selectable=True, color=text_color),
                ft.Row(
                    [
                        ft.Text(self._format_time(), size=9, color=ft.colors.ON_SURFACE_VARIANT),
                        ft.TextButton("复制", on_click=_copy),
                    ],
                    spacing=8,
                ),
            ],
            tight=True,
        )
        
        self.chat_list.controls.append(
            ft.Row(
                [
                    ft.Container(content, bgcolor=color, padding=10, border_radius=16, expand=True),
                ],
                alignment=align,
            )
        )
        self.chat_list.update()
    
    def _format_time(self) -> str:
        return datetime.now().strftime("%H:%M")
    
    def _clear_chat(self):
        self.chat_list.controls.clear()
        self.chat_list.update()
    
    def _append_terminal(self, text: str):
        self._terminal_lines.append(text)
        if len(self._terminal_lines) > 300:
            self._terminal_lines = self._terminal_lines[-300:]
        self.terminal_list.controls.clear()
        is_error = any(k in text.lower() for k in ["error", "err", "失败", "异常", "fail", "traceback", "error"])
        color = ft.colors.RED_400 if is_error else ft.colors.ON_SURFACE_VARIANT
        for line in self._terminal_lines[-80:]:
            self.terminal_list.controls.append(
                ft.Text(line, size=12, color=color, selectable=True)
            )
        self.terminal_list.update()
    
    def _append_mcp(self, text: str):
        self._mcp_logs.append(text)
        if len(self._mcp_logs) > 200:
            self._mcp_logs = self._mcp_logs[-200:]
        self.mcp_list.controls.clear()
        for line in self._mcp_logs[-80:]:
            self.mcp_list.controls.append(
                ft.Text(line, size=12, color=ft.colors.ON_SURFACE_VARIANT, selectable=True)
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
    
    def _set_status(self, text: str, color=ft.colors.GREEN_400):
        self.status_text.value = text
        self.status_text.color = color
        self.status_text.update()

    def _set_browser_status(self, connected: bool, text: str):
        self.browser_connected = connected
        self.browser_status_text.value = text
        self.browser_status_icon.color = ft.colors.GREEN_400 if connected else ft.colors.RED_400
        self.browser_status_icon.update()
        self.browser_status_text.update()
    
    def _save_config(self):
        prism_config.set("model.default", self.model_dropdown.value)
        prism_config.set("model.provider", self.provider_textfield.value)
        prism_config.set("model.base_url", "https://api.stepfun.com/step_plan/v1")
        prism_config.set("model.api_key", self.api_key_textfield.value)
        self._set_status("配置已保存")
        self._append_terminal("配置已保存")
        self.agent = create_agent()
    
    def _send(self):
        text = self.input_field.value.strip()
        if not text:
            return
        self._append("你", text)
        self.input_field.value = ""
        self.input_field.disabled = True
        self.input_field.update()
        self._set_status("思考中...", ft.colors.AMBER_400)
        self._append_terminal(f">>> {text}")
        
        try:
            reply = self.agent.chat(text)
        except Exception as e:
            reply = f"出错：{e}"
        
        self._append("PRISM", reply)
        self._append_terminal(f"<<< {reply}")
        self._set_status("就绪")
        self.input_field.disabled = False
        self.input_field.focus()
        self.input_field.update()
    
    def _browser_open(self):
        url = self.url_field.value.strip()
        if not url:
            self._set_status("请输入网址", ft.colors.RED_400)
            return
        self._set_status("正在打开网页...", ft.colors.AMBER_400)
        self._append_terminal(f"browser open {url}")
        result = open_page(url, headless=False)
        if result.get("success"):
            self._set_browser_status(True, f"已连接：{result.get('url', url)}")
            self._set_status(f"已打开：{result.get('url', url)}")
            self._append("浏览器", f"已打开：{result.get('url', url)}\n标题：{result.get('title', 'N/A')}")
            self._append_terminal(f"browser opened {result.get('url')}")
        else:
            self._set_browser_status(False, "打开失败")
            self._set_status(f"打开失败：{result.get('error')}", ft.colors.RED_400)
            self._append("浏览器", f"打开失败：{result.get('error')}")
            self._append_terminal(f"browser error: {result.get('error')}")
    
    def _browser_snapshot(self):
        if not self.browser_connected:
            self._set_status("浏览器未连接", ft.colors.RED_400)
            return
        self._set_status("正在读取页面...", ft.colors.AMBER_400)
        self._append_terminal("browser snapshot ...")
        result = page_snapshot()
        if result.get("success"):
            content = result.get("content", "") or "(空)"
            self._set_status(f"页面快照：{result.get('title', 'N/A')}")
            self._append("页面快照", f"URL：{result.get('url')}\n标题：{result.get('title')}\n\n{content[:1200]}")
            self._append_terminal(f"browser snapshot: {result.get('title')}")
        else:
            self._set_browser_status(False, "快照失败")
            self._set_status(f"快照失败：{result.get('error')}", ft.colors.RED_400)
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
            self._set_status(f"关闭失败：{result.get('error')}", ft.colors.RED_400)
            self._append("浏览器", f"关闭失败：{result.get('error')}")
            self._append_terminal(f"browser close error: {result.get('error')}")

    def _run_terminal_command(self):
        command = self.terminal_input.value.strip()
        if not command:
            return
        self._append_terminal(f">>> {command}")
        self.terminal_input.value = ""
        self.terminal_input.update()
        self._set_status("执行命令中...", ft.colors.AMBER_400)
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
                ft.Text("未配置 MCP 服务器", size=12, color=ft.colors.ON_SURFACE_VARIANT)
            )
        else:
            for idx, server in enumerate(raw):
                name = server.get("name") or server.get("id") or f"server_{idx+1}"
                status = "未启动"
                start_btn = ft.TextButton("启动", data=name)
                start_btn.on_click = lambda e, s=name, b=start_btn: self._toggle_mcp_server(s, b)
                log_btn = ft.TextButton("日志", data=name)
                log_btn.on_click = lambda e, s=name: self._show_mcp_log(s)
                row = ft.Row(
                    [
                        ft.Text(name, size=12, expand=True),
                        ft.Text(status, size=11, color=ft.colors.ON_SURFACE_VARIANT),
                        start_btn,
                        log_btn,
                    ]
                )
                self.mcp_server_list.controls.append(row)
        self.mcp_server_list.update()
        self._append_mcp(f"已刷新 MCP 服务器：{len(raw)} 个")

    def _toggle_mcp_server(self, name: str, button: ft.TextButton):
        self._append_terminal(f"mcp toggle {name}")
        try:
            current = self._mcp_server_status.get(name, False)
            self._mcp_server_status[name] = not current
            state = "已启动" if self._mcp_server_status[name] else "已停止"
            self._append_mcp(f"[{name}] {state}")
            button.text = "已启动" if self._mcp_server_status[name] else "启动"
            button.update()
        except Exception as e:
            self._append_mcp(f"[{name}] 切换失败：{e}")

    def _show_mcp_log(self, name: str):
        self._append_mcp(f"[{name}] 日志入口后续接入真实 MCP 客户端")
        self._append_terminal(f"mcp log {name}")

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
                ft.Text("暂无可用 Skills", size=12, color=ft.colors.ON_SURFACE_VARIANT)
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
                            ft.Text(status, size=11, color=ft.colors.ON_SURFACE_VARIANT),
                            toggle,
                            run_btn,
                        ]
                    )
                )
                if desc:
                    self.skill_list.controls.append(
                        ft.Text(desc, size=11, color=ft.colors.ON_SURFACE_VARIANT)
                    )
                if trigger_text:
                    self.skill_list.controls.append(
                        ft.Text(f"触发词：{trigger_text}", size=10, color=ft.colors.ON_SURFACE_VARIANT)
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
            self._set_status("请输入 Skill 名称或本地路径", ft.colors.RED_400)
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
                self._set_status("Skill 安装失败", ft.colors.RED_400)
        except Exception as e:
            self._append_mcp(f"[install] 异常：{e}")
            self._set_status("Skill 安装异常", ft.colors.RED_400)
        self.skill_install_field.value = ""
        self.skill_install_field.update()
        self._refresh_skills()

    def _save_session(self):
        name = (self.session_name_field.value or "").strip()
        if not name:
            self._set_status("请输入会话名称", ft.colors.RED_400)
            return
        try:
            path = self.agent.save_session(name)
            self._append_terminal(f"session saved: {path}")
            self._set_status("会话已保存")
        except Exception as e:
            self._append_terminal(f"session save failed: {e}")
            self._set_status("会话保存失败", ft.colors.RED_400)
        self.session_name_field.value = ""
        self.session_name_field.update()
        self._refresh_sessions()

    def _refresh_sessions(self):
        self.session_list.controls.clear()
        try:
            for name in self.agent.list_sessions():
                load_btn = ft.ElevatedButton(name, width=200)
                load_btn.on_click = lambda e, n=name: self._load_session(n)
                del_btn = ft.IconButton(icon=ft.icons.DELETE_OUTLINE, tooltip="删除会话")
                del_btn.on_click = lambda e, n=name: self._delete_session(n)
                self.session_list.controls.append(
                    ft.Row([load_btn, del_btn], spacing=6)
                )
        except Exception:
            pass
        self.session_list.update()

    def _delete_session(self, name: str):
        try:
            ok = self.agent.delete_session(name)
            self._append_terminal(f"session delete {name}: {'ok' if ok else 'failed'}")
            self._set_status("会话已删除" if ok else "删除失败", ft.colors.RED_400 if not ok else ft.colors.GREEN_400)
        except Exception as e:
            self._append_terminal(f"session delete error: {e}")
            self._set_status("删除异常", ft.colors.RED_400)
        self._refresh_sessions()

    def _load_session(self, name: str):
        try:
            ok = self.agent.load_session(name)
            if ok:
                self._append_terminal(f"session loaded: {name}")
                self._set_status("会话已加载")
                self.chat_list.controls.clear()
                for m in self.agent.messages:
                    if m.role == "system":
                        continue
                    role_label = "你" if m.role == "user" else ("PRISM" if m.role == "assistant" else m.role)
                    self._append(role_label, m.content or "")
                self.chat_list.update()
            else:
                self._append_terminal(f"session load failed: {name}")
                self._set_status("会话加载失败", ft.colors.RED_400)
        except Exception as e:
            self._append_terminal(f"session load error: {e}")
            self._set_status("会话加载异常", ft.colors.RED_400)


def main():
    ft.app(target=lambda page: PrismDesktop(page))


if __name__ == "__main__":
    main()
