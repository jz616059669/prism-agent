"""
PRISM Agent - 桌面客户端
基于 Flet 实现，比 Codex CLI 更现代
"""

import flet as ft
from typing import Optional


class PrismDesktop:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "PRISM Agent"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.padding = 24
        self.page.window_width = 1100
        self.page.window_height = 720
        self.page.theme = ft.Theme(color_scheme_seed="blue")
        
        self.messages = []
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
            value="step-3.7-flash",
            options=[ft.dropdown.Option("step-3.7-flash"), ft.dropdown.Option("gpt-4o")],
            width=220,
        )
        self.provider_textfield = ft.TextField(
            label="提供商",
            value="stepfun",
            password=True,
            can_reveal_password=True,
            width=220,
        )
        self.api_key_textfield = ft.TextField(
            label="API Key",
            value="",
            password=True,
            can_reveal_password=True,
            width=220,
        )
        self.status_text = ft.Text("就绪", size=12, color=ft.colors.GREEN_400)
        
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("PRISM", size=20, weight=ft.FontWeight.BOLD),
                    ft.Divider(height=12, color=ft.colors.TRANSPARENT),
                    self.model_dropdown,
                    ft.Container(height=8),
                    self.provider_textfield,
                    ft.Container(height=8),
                    self.api_key_textfield,
                    ft.Container(height=8),
                    ft.ElevatedButton("保存配置", width=220),
                    ft.Container(height=16),
                    self.status_text,
                    ft.Text("浏览器 / 终端 / MCP 能力即将接入桌面控制", size=11, color=ft.colors.GREY_400),
                ],
                tight=True,
                spacing=6,
            ),
            width=260,
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
    
    def _send(self):
        text = self.input_field.value.strip()
        if not text:
            return
        self._append("你", text)
        self.input_field.value = ""
        self.input_field.update()
        self.status_text.value = "思考中..."
        self.status_text.color = ft.colors.AMBER_400
        self.status_text.update()
        
        # 占位回复，后续接入 prism agent
        self._append("PRISM", f"已收到：{text}\n桌面客户端已连通。")
        self.status_text.value = "就绪"
        self.status_text.color = ft.colors.GREEN_400
        self.status_text.update()


def main():
    ft.app(target=lambda page: PrismDesktop(page))


if __name__ == "__main__":
    main()
