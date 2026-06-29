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


def _append(
    self,
    role: str,
    text: str,
    retry: bool = False,
    retry_text: str = "",
    placeholder: bool = False,
):
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
                _markdown_to_ft(self, rendered),
                ft.Text(timestamp, size=10, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.END),
            ],
            tight=True,
            spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.END,
        )
    else:
        content_widget = ft.Column(
            [
                _markdown_to_ft(self, rendered),
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
    max_chat_items = 500
    if len(self.chat_list.controls) > max_chat_items:
        self.chat_list.controls = self.chat_list.controls[-max_chat_items:]
    # scroll_to removed for Flet 0.85.3 compatibility
    self.chat_list.update()
    if placeholder:
        return ft.Container(
            content=message_row,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=16,
            padding=ft.Padding(12, 10, 12, 10),
        )
    return message_row


def _clear_chat(self):
    self.chat_list.controls.clear()
    if hasattr(self, "_chat_placeholder") and self._chat_placeholder:
        self.chat_list.controls.append(self._chat_placeholder)
    self.chat_list.update()
    if hasattr(self, "_update_input_count"):
        self._update_input_count()


def _show_message_menu(self, e, target, message_text: str):
    try:
        self.page.set_clipboard(message_text)
        self._set_status("已复制", ft.Colors.GREEN_400)
    except Exception:
        pass


def _on_input_change(self):
    try:
        text = self.input_field.value or ""
        self.input_count.value = f"{len(text)} 字"
        self.input_count.update()
    except Exception:
        pass


def _send(self, retry_text: str = ""):
    try:
        text = retry_text or (self.input_field.value or "").strip()
    except Exception:
        return
    if not text:
        return
    _append(self, "你", text)
    self.input_field.value = ""
    self.input_field.disabled = True
    self.send_btn.visible = False
    self.stop_btn.visible = True
    self.input_field.update()
    self.send_btn.update()
    self.stop_btn.update()
    self._set_status("PRISM 正在思考...", ft.Colors.AMBER_400)
    placeholder = _append(self, "PRISM", "", placeholder=True)
    try:
        reply = self.agent.chat(text) or "(无回复)"
    except Exception as e:
        reply = f"Error: {e}"
    placeholder.controls[0].content.controls[1] = _markdown_to_ft(self, reply)
    placeholder.controls[0].content.controls[0].color = ft.Colors.ON_SURFACE_VARIANT
    placeholder.controls[0].bgcolor = ft.Colors.SURFACE_CONTAINER
    placeholder.update()
    # scroll_to removed for Flet 0.85.3 compatibility
    self.input_field.disabled = False
    self.send_btn.visible = True
    self.stop_btn.visible = False
    self.send_btn.update()
    self.stop_btn.update()
    self._set_status("就绪", ft.Colors.GREEN_400)
    try:
        self.input_field.focus()
    except Exception:
        pass

