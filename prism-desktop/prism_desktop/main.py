"""
PRISM Agent - 桌面客户端
基于 Flet 实现，比 Codex CLI 更现代
已连通真实 Agent 后端 + 浏览器控制
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
        self.page.padding = 24
        self.page.window_width = 1200
        self.page.window_height = 760
        self.page.theme = ft.Theme(color_scheme_seed="blue")
        
        self.messages = []
        self.agent = create_agent()
        self.browser_connected = False
        self._build_ui()
    
    def _build_ui(self):
        self.page.add(
            ft.Row(
                [
                    self._build_sidebar(),
                    ft.VerticalDivider(width=1),
                    self._build_chat(),
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
            width=240,
        )
        self.provider_textfield = ft.TextField(
            label="提供商",
            value=prism_config.get("model.provider", "stepfun"),
            password=True,
            can_reveal_password=True,
            width=240,
        )
        self.api_key_textfield = ft.TextField(
            label="API Key",
            value=prism_config.get("model.api_key", ""),
            password=True,
            can_reveal_password=True,
            width=240,
        )
        self.status_text = ft.Text("就绪", size=12, color=ft.colors.GREEN_400)
        
        save_btn = ft.ElevatedButton("保存配置", width=240)
        save_btn.on_click = lambda e: self._save_config()
        
        self.url_field = ft.TextField(
            hint_text="输入网址...",
            value="https://example.com",
            width=240,
        )
        browser_open_btn = ft.ElevatedButton("打开网页", width=240)
        browser_open_btn.on_click = lambda e: self._browser_open()
        
        browser_snapshot_btn = ft.ElevatedButton("读取页面快照", width=240)
        browser_snapshot_btn.on_click = lambda e: self._browser_snapshot()
        
        browser_close_btn = ft.ElevatedButton("关闭浏览器", width=240)
        browser_close_btn.on_click = lambda e: self._browser_close()
        
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
                    self.status_text,
                    ft.Text("终端 / MCP 控制后续接入", size=11, color=ft.colors.GREY_400),
                ],
                tight=True,
                spacing=6,
            ),
            width=270,
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
        self.agent = create_agent()
    
    def _send(self):
        text = self.input_field.value.strip()
        if not text:
            return
        self._append("你", text)
        self.input_field.value = ""
        self.input_field.update()
        self._set_status("思考中...", ft.colors.AMBER_400)
        
        try:
            reply = self.agent.chat(text)
        except Exception as e:
            reply = f"出错：{e}"
        
        self._append("PRISM", reply)
        self._set_status("就绪")
    
    def _browser_open(self):
        url = self.url_field.value.strip()
        if not url:
            self._set_status("请输入网址", ft.colors.RED_400)
            return
        self._set_status("正在打开网页...", ft.colors.AMBER_400)
        result = open_page(url, headless=False)
        if result.get("success"):
            self.browser_connected = True
            self._set_status(f"已打开：{result.get('url', url)}")
            self._append("浏览器", f"已打开：{result.get('url', url)}\n标题：{result.get('title', 'N/A')}")
        else:
            self.browser_connected = False
            self._set_status(f"打开失败：{result.get('error')}", ft.colors.RED_400)
            self._append("浏览器", f"打开失败：{result.get('error')}")
    
    def _browser_snapshot(self):
        if not self.browser_connected:
            self._set_status("浏览器未连接", ft.colors.RED_400)
            return
        self._set_status("正在读取页面...", ft.colors.AMBER_400)
        result = page_snapshot()
        if result.get("success"):
            content = result.get("content", "") or "(空)"
            self._set_status(f"页面快照：{result.get('title', 'N/A')}")
            self._append("页面快照", f"URL：{result.get('url')}\n标题：{result.get('title')}\n\n{content[:1200]}")
        else:
            self._set_status(f"快照失败：{result.get('error')}", ft.colors.RED_400)
            self._append("页面快照", f"失败：{result.get('error')}")
    
    def _browser_close(self):
        result = close_browser()
        self.browser_connected = False
        if result.get("success"):
            self._set_status("浏览器已关闭")
            self._append("浏览器", "浏览器已关闭")
        else:
            self._set_status(f"关闭失败：{result.get('error')}", ft.colors.RED_400)
            self._append("浏览器", f"关闭失败：{result.get('error')}")


def main():
    ft.app(target=lambda page: PrismDesktop(page))


if __name__ == "__main__":
    main()
