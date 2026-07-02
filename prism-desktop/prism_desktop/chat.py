"""PRISM Desktop - 聊天与消息 UI"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, List, Tuple

import markdown
import flet as ft

from prism.logging import logger
import traceback

if TYPE_CHECKING:
    from prism_desktop.main import PrismDesktop


class ChatMixin:
    def _format_time(self) -> str:
        import datetime
        return datetime.datetime.now().strftime("%H:%M")

    def _markdown_to_ft(self, text: str) -> List[ft.Control]:
        is_error = False
        try:
            rendered = markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br", "pymdownx.arithmatex"])
        except Exception:
            logger.debug("markdown render failed: %s", traceback.format_exc())
            try:
                rendered = markdown.markdown(text, extensions=["fenced_code", "tables", "nl2br"])
            except Exception:
                logger.debug("markdown fallback render failed: %s", traceback.format_exc())
                rendered = text
        is_error = text.startswith("Error:") or text.startswith("请求超时") or text.startswith("失败")
        display_color = ft.Colors.ERROR if is_error else ft.Colors.ON_SURFACE
        return [
            ft.Text(rendered, selectable=True, color=display_color),
        ]

    def _append(self, role: str, text: str, retry: bool = False, retry_text: str = "", placeholder: bool = False):
        if hasattr(self, "_chat_placeholder") and self._chat_placeholder and self._chat_placeholder in self.chat_list.controls:
            self.chat_list.controls.remove(self._chat_placeholder)
        is_user = role == "你"
        align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        text_color = ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M")
        try:
            role_text = ft.Text(role, size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500)
            time_text = ft.Text(timestamp, size=11, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.8)
            content = self._markdown_to_ft(text)
            row = ft.Row(
                [role_text, ft.Container(expand=True), time_text],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            bubble = ft.Container(
                content=ft.Column(
                    [row, ft.Container(height=4), *content],
                    tight=True,
                    spacing=0,
                ),
                padding=ft.Padding(14, 10, 14, 10),
                bgcolor=ft.Colors.PRIMARY_CONTAINER if is_user else ft.Colors.SURFACE_CONTAINER,
                border_radius=ft.RoundedRectangleBorder(radius=18),
                border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
                width=420,
            )
            self.chat_list.controls.append(ft.Container(bubble, alignment=align))
            self.chat_list.update()
        except Exception:
            logger.debug("append message failed: %s", traceback.format_exc())
            try:
                self._append_terminal(f"[CHAT ERROR] {role}: {text[:200]}")
            except Exception:
                pass

    def _clear_chat(self):
        try:
            self.chat_list.controls.clear()
            self.chat_list.controls.append(self._chat_placeholder)
            self.chat_list.update()
        except Exception:
            logger.debug("clear chat failed: %s", traceback.format_exc())
            pass

    def _send(self, retry_text: str = ""):
        text = retry_text or (self.input_field.value or "").strip()
        if not text:
            return
        self.input_field.value = ""
        self.input_field.update()
        self._generating = True
        self.stop_btn.visible = True
        self.stop_btn.update()
        self._append("你", text)
        try:
            self.agent.chat(text, on_chunk=lambda c: self._append("PRISM", c) if not getattr(self, "_generating", False) else None)
        except Exception as exc:
            self._append("PRISM", f"Error: {exc}")
        finally:
            self._generating = False
            try:
                self.stop_btn.visible = False
                self.stop_btn.update()
            except Exception:
                pass

    def _stop_send(self):
        self._generating = False

    def _search_messages(self, query: str):
        if not query:
            return
        items = getattr(self.chat_list, "controls", [])
        for idx, item in enumerate(items):
            text = ""
            if hasattr(item, "content") and hasattr(item.content, "content"):
                try:
                    for ctrl in item.content.content.controls:
                        if hasattr(ctrl, "value"):
                            text += str(ctrl.value)
                except Exception:
                    pass
            if query in text:
                try:
                    self.chat_list.scroll_to(idx=idx, duration=200)
                except Exception:
                    pass
                return

    def _jump_to_next_match(self, query: str):
        self._search_messages(query)

    def _prev_match(self, query: str):
        self._search_messages(query)

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
        except Exception:
            logger.debug("apply prompt template failed: %s", traceback.format_exc())
            pass
