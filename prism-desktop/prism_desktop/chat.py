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
from prism_desktop.i18n import gettext as _
import markdown
import subprocess

DRAFTS_PATH = Path.home() / '.prism' / 'drafts.json'

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


_CODE_COPY_SCRIPT = """
<script>
function prismCopyCode(btn) {
    const pre = btn.closest('pre');
    const code = pre.querySelector('code');
    const text = code ? code.innerText : pre.innerText;
    navigator.clipboard.writeText(text).then(() => {
        btn.innerText = '已复制';
        setTimeout(() => btn.innerText = '复制', 1500);
    }).catch(() => {
        btn.innerText = '失败';
        setTimeout(() => btn.innerText = '复制', 1500);
    });
}
</script>
"""

def _markdown_to_ft(self, text: str):
    html = markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br"])
    # Inject copy button into each code block
    if "<pre><code>" in html:
        html = html.replace("<pre><code>", "<pre><code>")
        parts = html.split("</code></pre>")
        if len(parts) > 1:
            new_parts = []
            for idx, part in enumerate(parts[:-1]):
                new_parts.append(part + "</code></pre>")
                new_parts.append(
                    '<button onclick="prismCopyCode(this)" '
                    'style="position:absolute;top:8px;right:12px;'
                    'background:rgba(255,255,255,0.12);color:#fff;'
                    'border:none;border-radius:8px;padding:4px 10px;'
                    'font-size:12px;cursor:pointer;backdrop-filter:blur(4px);">复制</button>'
                )
            new_parts.append(parts[-1])
            html = "".join(new_parts)
        html = _CODE_COPY_SCRIPT + html
    return ft.Markdown(
        value=html,
        selectable=True,
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        code_theme="monokai",
        code_block_style=ft.CodeBlockStyle(
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
            border_radius=12,
            padding=ft.Padding(12, 10, 12, 10),
        ),
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
        rendered = markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br", "pymdownx.arithmatex"])
    except Exception:
        try:
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
    message_container = ft.GestureDetector(
        content=message_row,
        on_long_press=lambda e, row=message_row: self._show_message_menu(e, row, text),
    )
    self.chat_list.controls.append(message_container)
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


def _build_prompt_templates(self) -> ft.Column:
    templates = [
        ("翻译助手", "请将以下内容翻译成英文：\n"),
        ("代码解释", "请解释以下代码的功能和逻辑：\n"),
        ("总结摘要", "请用简短的几句话总结以下内容：\n"),
        ("纠错润色", "请检查并修正以下文本中的语法和表达问题：\n"),
        ("头脑风暴", "请针对以下主题提供创意想法和建议：\n"),
    ]
    buttons = []
    for title, prompt in templates:
        btn = ft.TextButton(
            title,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                color=ft.Colors.ON_SURFACE,
            ),
            on_click=lambda e, p=prompt: self._apply_prompt_template(p),
        )
        buttons.append(btn)
    return ft.Column(buttons, spacing=6, tight=True)

def _apply_prompt_template(self, prompt: str):
    try:
        current = self.input_field.value or ""
        self.input_field.value = prompt + current
        self.input_field.focus()
        self.input_field.update()
        if hasattr(self, "_update_input_count"):
            self._update_input_count()
    except Exception:
        pass

def _clear_chat(self):
    self.chat_list.controls.clear()
    if hasattr(self, "_chat_placeholder") and self._chat_placeholder:
        self.chat_list.controls.append(self._chat_placeholder)
    self.chat_list.update()
    if hasattr(self, "_update_input_count"):
        self._update_input_count()


def _show_message_menu(self, e, target, message_text: str):
    def _close(_):
        try:
            self.page.close_dialog()
        except Exception:
            pass
    def _copy(_):
        try:
            self.page.set_clipboard(message_text)
            self._set_status("已复制", ft.Colors.GREEN_400)
            self.page.close_dialog()
        except Exception:
            pass
    def _delete(_):
        try:
            self._delete_message(target)
            self._set_status("已删除", ft.Colors.GREEN_400)
            self.page.close_dialog()
        except Exception:
            pass
    def _pin(_):
        try:
            self._pin_message(target)
            self._set_status("已置顶", ft.Colors.GREEN_400)
            self.page.close_dialog()
        except Exception:
            pass
    self.page.dialog = ft.AlertDialog(
        title=ft.Text("消息操作"),
        content=ft.Text(message_text[:100] + ("..." if len(message_text) > 100 else ""), max_lines=3, overflow=ft.TextOverflow.ELLIPSIS),
        actions=[
            ft.TextButton("复制", on_click=_copy),
            ft.TextButton("删除", on_click=_delete),
            ft.TextButton("置顶", on_click=_pin),
            ft.TextButton("关闭", on_click=_close),
        ],
    )
    self.page.dialog.open = True
    self.page.update()


def _delete_message(self, message_row):
    try:
        if message_row in self.chat_list.controls:
            self.chat_list.controls.remove(message_row)
            self.chat_list.update()
    except Exception:
        pass

def _pin_message(self, message_row):
    try:
        # Pin by prepending to controls (visual top)
        if message_row in self.chat_list.controls:
            self.chat_list.controls.remove(message_row)
            self.chat_list.controls.insert(0, message_row)
            self.chat_list.update()
    except Exception:
        pass


    def _search_messages(self, query: str):
        if not query or not hasattr(self, "chat_list"):
            return
        query = query.lower()
        found = 0
        for idx, control in enumerate(self.chat_list.controls):
            try:
                text = ""
                if hasattr(control, "content") and hasattr(control.content, "controls"):
                    for c in control.content.controls:
                        if hasattr(c, "value") and isinstance(getattr(c, "value", None), str):
                            text += c.value
                if query and query in text.lower():
                    found += 1
                    try:
                        control.bgcolor = ft.Colors.with_opacity(0.18, ft.Colors.PRIMARY)
                    except Exception:
                        pass
                else:
                    try:
                        control.bgcolor = None
                    except Exception:
                        pass
            except Exception:
                pass
        self.chat_list.update()
        self._set_status(f"搜索完成：找到 {found} 条", ft.Colors.GREEN_400 if found else ft.Colors.AMBER_400)

    def _jump_to_next_match(self, query: str):
        if not query or not hasattr(self, "chat_list"):
            return
        query = query.lower()
        start = getattr(self, "_search_cursor", -1) + 1
        controls = getattr(self.chat_list, "controls", [])
        for idx in range(start, len(controls)):
            control = controls[idx]
            try:
                text = ""
                if hasattr(control, "content") and hasattr(control.content, "controls"):
                    for c in control.content.controls:
                        if hasattr(c, "value") and isinstance(getattr(c, "value", None), str):
                            text += c.value
                if query and query in text.lower():
                    self._search_cursor = idx
                    self.chat_list.scroll_to(idx=idx)
                    self.chat_list.update()
                    self._set_status(f"定位到第 {idx + 1} 条", ft.Colors.GREEN_400)
                    return
            except Exception:
                pass
        self._set_status("已到最后一条", ft.Colors.AMBER_400)

    def _prev_match(self, query: str):
        if not query or not hasattr(self, "chat_list"):
            return
        query = query.lower()
        controls = getattr(self.chat_list, "controls", [])
        start = getattr(self, "_search_cursor", len(controls))
        for idx in range(start - 1, -1, -1):
            control = controls[idx]
            try:
                text = ""
                if hasattr(control, "content") and hasattr(control.content, "controls"):
                    for c in control.content.controls:
                        if hasattr(c, "value") and isinstance(getattr(c, "value", None), str):
                            text += c.value
                if query and query in text.lower():
                    self._search_cursor = idx
                    self.chat_list.scroll_to(idx=idx)
                    self.chat_list.update()
                    self._set_status(f"定位到第 {idx + 1} 条", ft.Colors.GREEN_400)
                    return
            except Exception:
                pass
        self._set_status("已到第一条", ft.Colors.AMBER_400)


def _on_input_change(self):
    try:
        text = self.input_field.value or ""
        self.input_count.value = f"{len(text)} 字"
        self.input_count.update()
        # Auto-save draft
        try:
            DRAFTS_PATH.write_text(text, encoding="utf-8")
        except Exception:
            pass
    except Exception:
        pass

def _terminal_history_up(self):
    try:
        if not hasattr(self, "_terminal_history"):
            self._terminal_history = []
            self._terminal_history_index = -1
        if not self._terminal_history:
            return
        current = self.input_field.value or ""
        if self._terminal_history_index == -1:
            self._terminal_history_buffer = current
        self._terminal_history_index = max(0, self._terminal_history_index - 1)
        self.input_field.value = self._terminal_history[self._terminal_history_index]
        self.input_field.update()
    except Exception:
        pass

def _terminal_history_down(self):
    try:
        if not hasattr(self, "_terminal_history"):
            self._terminal_history = []
            self._terminal_history_index = -1
        if not self._terminal_history:
            return
        if self._terminal_history_index + 1 >= len(self._terminal_history):
            self.input_field.value = getattr(self, "_terminal_history_buffer", "")
            self._terminal_history_index = len(self._terminal_history)
        else:
            self._terminal_history_index += 1
            self.input_field.value = self._terminal_history[self._terminal_history_index]
        self.input_field.update()
    except Exception:
        pass


def _send(self, retry_text: str = ""):
    try:
        text = retry_text or (self.input_field.value or "").strip()
    except Exception:
        return
    if not text:
        # Try restore from draft
        try:
            draft = DRAFTS_PATH.read_text(encoding="utf-8")
            if draft.strip():
                text = draft.strip()
                self.input_field.value = ""
                self.input_field.update()
        except Exception:
            pass
    if not text:
        return
    _append(self, "你", text)
    self.input_field.value = ""
    self.input_field.disabled = True
    self.send_btn.visible = False
    self.stop_btn.visible = True
    self._generating = True
    self.input_field.update()
    self.send_btn.update()
    self.stop_btn.update()
    self._set_status("PRISM 正在思考...", ft.Colors.AMBER_400)
    try:
        self._log_to_file("info", "stream_start", model=getattr(self, "model_dropdown", None) and self.model_dropdown.value, provider=getattr(self, "provider_textfield", None) and self.provider_textfield.value)
    except Exception:
        pass
    placeholder = _append(self, "PRISM", "", placeholder=True)
    stream_text = [""]

    def on_chunk(chunk: str):
        if not getattr(self, "_generating", True):
            return
        stream_text[0] += chunk
        try:
            self._chunk_count = getattr(self, "_chunk_count", 0) + 1
        except Exception:
            pass
        try:
            # Typewriter effect: render full accumulated text through markdown
            rendered = markdown.markdown(stream_text[0], extensions=["fenced_code", "tables", "nl2br", "pymdownx.arithmatex"]) if stream_text[0] else ""
            placeholder.controls[0].content.controls[1] = _markdown_to_ft(self, rendered)
            placeholder.update()
        except Exception:
            pass

    try:
        result = self.agent.chat(text, on_stream=on_chunk, stop_callback=lambda: not getattr(self, "_generating", True)) or "(无回复)"
        reply = result if isinstance(result, str) else result.get("content", "(无回复)")
    except Exception as e:
        reply = f"Error: {e}"
    placeholder.controls[0].content.controls[1] = _markdown_to_ft(self, reply)
    placeholder.controls[0].content.controls[0].color = ft.Colors.ON_SURFACE_VARIANT
    placeholder.controls[0].bgcolor = ft.Colors.SURFACE_CONTAINER
    placeholder.update()
    # scroll_to removed for Flet 0.85.3 compatibility
    self.input_field.disabled = False
    self.send_btn.visible = True
    self.send_btn.disabled = False
    self.stop_btn.visible = False
    self.send_btn.update()
    self.stop_btn.update()
    self._generating = False
    self._set_status("就绪", ft.Colors.GREEN_400)
    try:
        self._log_to_file("info", "stream_complete", chunks=getattr(self, "_chunk_count", 0))
    except Exception:
        pass
    try:
        self.input_field.focus()
    except Exception:
        pass

