"""
PRISM Agent - 桌面客户端
基于 Flet 实现，比 Codex CLI 更现代
已连通真实 Agent 后端 + 浏览器控制 + 终端输出 + MCP 控制
"""

import sys
from pathlib import Path
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
        
        self.messages = []
        self.agent = create_agent()
        self.browser_connected = False
        self._terminal_lines = ["PRISM Desktop 已启动"]
        self._mcp_logs = []
        self._build_ui()
    
    def _build_ui(self):
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
                    ft.Text("状态", size=12, weight=ft.FontWeight.BOLD),
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
        
        return ft.Column(
            [
                ft.Text("对话", size=18, weight=ft.FontWeight.BOLD),
                ft.Divider(height=8),
                ft.Container(self.chat_list, expand=True, border=ft.border.all(1, ft.colors.OUTLINE_VARIANT), border_radius=12, padding=12),
                ft.Divider(height=8),
                ft.Row([self.input_field, send_btn], spacing=8),
            ],
            expand=True,
            spacing=8,
        )
    
    def _build_right_panel(self) -> ft.Column:
        self.terminal_list = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        self.mcp_list = ft.ListView(expand=True, spacing=4, auto_scroll=True)
        
        clear_terminal_btn = ft.TextButton("清空终端")
        clear_terminal_btn.on_click = lambda e: self._clear_terminal()
        clear_mcp_btn = ft.TextButton("清空 MCP")
        clear_mcp_btn.on_click = lambda e: self._clear_mcp()
        
        return ft.Column(
            [
                ft.Text("终端", size=14, weight=ft.FontWeight.BOLD),
                ft.Row([clear_terminal_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(self.terminal_list, expand=True, border=ft.border.all(1, ft.colors.OUTLINE_VARIANT), border_radius=12, padding=12, bgcolor=ft.colors.SURFACE),
                ft.Divider(height=12),
                ft.Text("MCP", size=14, weight=ft.FontWeight.BOLD),
                ft.Row([clear_mcp_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(self.mcp_list, expand=True, border=ft.border.all(1, ft.colors.OUTLINE_VARIANT), border_radius=12, padding=12, bgcolor=ft.colors.SURFACE),
            ],
            expand=True,
            spacing=8,
        )
    
    def _append(self, role: str, text: str):
        self.chat_list.controls.append(
            ft.Row(
                [
                    ft.Container(
                        ft.Text(role, size=11, color=ft.colors.ON_SURFACE_VARIANT),
                        width=64,
                    ),
                    ft.Container(
                        ft.Text(text, selectable=True),
                        bgcolor=ft.colors.SURFACE_VARIANT,
                        padding=10,
                        border_radius=12,
                        expand=True,
                    ),
                ],
                tight=True,
            )
        )
        self.chat_list.update()
    
    def _append_terminal(self, text: str):
        self._terminal_lines.append(text)
        if len(self._terminal_lines) > 300:
            self._terminal_lines = self._terminal_lines[-300:]
        self.terminal_list.controls.clear()
        for line in self._terminal_lines[-80:]:
            self.terminal_list.controls.append(
                ft.Text(line, size=12, color=ft.colors.ON_SURFACE_VARIANT, selectable=True)
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
    
    def _browser_open(self):
        url = self.url_field.value.strip()
        if not url:
            self._set_status("请输入网址", ft.colors.RED_400)
            return
        self._set_status("正在打开网页...", ft.colors.AMBER_400)
        self._append_terminal(f"browser open {url}")
        result = open_page(url, headless=False)
        if result.get("success"):
            self.browser_connected = True
            self._set_status(f"已打开：{result.get('url', url)}")
            self._append("浏览器", f"已打开：{result.get('url', url)}\n标题：{result.get('title', 'N/A')}")
            self._append_terminal(f"browser opened {result.get('url')}")
        else:
            self.browser_connected = False
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
            self._set_status(f"快照失败：{result.get('error')}", ft.colors.RED_400)
            self._append("页面快照", f"失败：{result.get('error')}")
            self._append_terminal(f"browser snapshot error: {result.get('error')}")
    
    def _browser_close(self):
        self._append_terminal("browser close ...")
        result = close_browser()
        self.browser_connected = False
        if result.get("success"):
            self._set_status("浏览器已关闭")
            self._append("浏览器", "浏览器已关闭")
            self._append_terminal("browser closed")
        else:
            self._set_status(f"关闭失败：{result.get('error')}", ft.colors.RED_400)
            self._append("浏览器", f"关闭失败：{result.get('error')}")
            self._append_terminal(f"browser close error: {result.get('error')}")

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
                row = ft.Row(
                    [
                        ft.Text(name, size=12, expand=True),
                        ft.Text(status, size=11, color=ft.colors.ON_SURFACE_VARIANT),
                        ft.TextButton("日志", data=name),
                    ]
                )
                row.controls[2].on_click = lambda e, s=name: self._show_mcp_log(s)
                self.mcp_server_list.controls.append(row)
        self.mcp_server_list.update()
        self._append_mcp(f"已刷新 MCP 服务器：{len(raw)} 个")

    def _show_mcp_log(self, name: str):
        self._append_mcp(f"[{name}] 日志入口后续接入真实 MCP 客户端")
        self._append_terminal(f"mcp log {name}")


def main():
    ft.app(target=lambda page: PrismDesktop(page))


if __name__ == "__main__":
    main()
