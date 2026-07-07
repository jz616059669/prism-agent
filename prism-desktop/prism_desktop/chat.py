"""PRISM Desktop - 聊天与消息 UI"""
from __future__ import annotations

import datetime
import json
from typing import TYPE_CHECKING, List, Tuple

import flet as ft

from prism.logging import logger
import traceback

if TYPE_CHECKING:
    from prism_desktop.main import PrismDesktop


class ChatMixin:
    def _format_time(self) -> str:
        return datetime.now().strftime("%H:%M")

    def _markdown_to_ft(self, text: str, text_color=ft.Colors.ON_SURFACE) -> List[ft.Control]:
        if not text or not text.strip():
            return [ft.Text(" ", selectable=True, color=text_color)]
        return [ft.Text(text, selectable=True, color=text_color)]

    def _append(self, role: str, text: str, retry: bool = False, retry_text: str = "", placeholder: bool = False):
        if hasattr(self, "_chat_placeholder") and self._chat_placeholder and self._chat_placeholder in self.chat_list.controls:
            self.chat_list.controls.remove(self._chat_placeholder)
        if hasattr(self, "_chat_placeholder") and self._chat_placeholder:
            try:
                self._chat_placeholder.visible = False
                if hasattr(self._chat_placeholder, "parent") and self._chat_placeholder.parent:
                    self._chat_placeholder.update()
            except Exception:
                logger.debug("hide placeholder failed: %s", traceback.format_exc())
        is_user = role == "你"
        align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        text_color = ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE
        timestamp = datetime.now().strftime("%H:%M")
        try:
            role_text = ft.Text(role, size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500)
            time_text = ft.Text(timestamp, size=11, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.8)
            content = self._markdown_to_ft(text, text_color=text_color)
            row = ft.Row(
                [role_text, ft.Container(expand=True), time_text],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            )
            message_widget = ft.Container(
                content=ft.Column(
                    [row, ft.Container(height=4), *content],
                    tight=True,
                    spacing=0,
                    horizontal_alignment=align,
                ),
                padding=ft.Padding(14, 10, 14, 10),
                bgcolor=ft.Colors.SURFACE_CONTAINER if not is_user else ft.Colors.PRIMARY_CONTAINER,
            )
            self.chat_list.controls.append(message_widget)
            try:
                self.chat_list.update()
            except Exception:
                logger.debug("chat_list update failed: %s", traceback.format_exc())
            try:
                self.page.update()
            except Exception:
                logger.debug("page update failed: %s", traceback.format_exc())
            try:
                if hasattr(self.chat_list, "scroll_to"):
                    self.chat_list.scroll_to(delta=99999, duration=150)
            except Exception:
                logger.debug("chat scroll failed: %s", traceback.format_exc())
        except Exception:
            logger.debug("append message failed: %s", traceback.format_exc())
            try:
                self._append_terminal(f"[CHAT ERROR] {role}: {text[:200]}")
            except Exception as ex:
                logger.debug("append message fallback failed: %s", ex)

    def _clear_chat(self):
        try:
            self.chat_list.controls.clear()
            self.chat_list.controls.append(self._chat_placeholder)
            self.page.update(self.chat_list)
        except Exception:
            logger.debug("clear chat failed: %s", traceback.format_exc())
            logger.warning("clear chat failed", exc_info=True)

    def _send(self, retry_text: str = ""):
        text = retry_text or (self.input_field.value or "").strip()
        if not text:
            return
        if not getattr(self, "agent", None):
            self._append("PRISM", "Error: agent 未初始化，请检查配置并保存后重试。")
            self._log_to_file("warning", "send_blocked", reason="agent is None")
            return
        self.input_field.value = ""
        self.input_field.update()
        self._generating = True
        self.stop_btn.visible = True
        self.stop_btn.update()
        self._append("你", text)

        stream_widget = None
        stream_text = ""
        _last_update = [0.0]

        def _throttled_update(w, value: str):
            now = __import__("time").time()
            if now - _last_update[0] >= 0.08 or not value:
                try:
                    stream_content = w.content.controls[2]
                    stream_content.value = value
                    w.update()
                    _last_update[0] = now
                except Exception:
                    logger.debug("stream chunk update failed: %s", traceback.format_exc())

        def _ensure_stream_widget():
            nonlocal stream_widget
            if stream_widget is None:
                role_text = ft.Text("PRISM", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500)
                timestamp = datetime.now().strftime("%H:%M")
                time_text = ft.Text(timestamp, size=11, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.8)
                stream_content = ft.Text("", selectable=True, color=ft.Colors.ON_SURFACE)
                row = ft.Row(
                    [role_text, ft.Container(expand=True), time_text],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
                stream_widget = ft.Container(
                    content=ft.Column(
                        [row, ft.Container(height=4), stream_content],
                        tight=True,
                        spacing=0,
                        horizontal_alignment=ft.MainAxisAlignment.START,
                    ),
                    padding=ft.Padding(14, 10, 14, 10),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                )
                self.chat_list.controls.append(stream_widget)
                try:
                    self.chat_list.update()
                except Exception:
                    logger.debug("chat_list update failed: %s", traceback.format_exc())
                try:
                    self.page.update()
                except Exception:
                    logger.debug("page update failed: %s", traceback.format_exc())
            return stream_widget

        def _stream_chunk(c: str):
            nonlocal stream_text
            stream_text += c
            w = _ensure_stream_widget()
            _throttled_update(w, stream_text)

        def _run_chat():
            nonlocal stream_widget, stream_text
            try:
                self._log_to_file("info", "stream_start", text=text, model=getattr(self.agent, "model", "unknown"))
                result = self.agent.chat(
                    text,
                    on_chunk=lambda c: _stream_chunk(c) if getattr(self, "_generating", False) else None,
                )
                self._log_to_file("info", "chat_result", result_type=type(result).__name__, result_preview=str(result)[:200])
                if isinstance(result, dict):
                    if not result.get("success"):
                        self._append("PRISM", f"Error: {result.get('error', 'Unknown error')}")
                    elif result.get("content"):
                        self._append("PRISM", result["content"])
                    else:
                        self._append("PRISM", " ")
                elif isinstance(result, str):
                    if result:
                        self._append("PRISM", result)
                    else:
                        self._append("PRISM", " ")
                else:
                    self._append("PRISM", f"Error: 未知返回类型 {type(result).__name__}")
            except Exception as exc:
                self._append("PRISM", f"Error: {exc}")
                self._log_to_file("error", "send_exception", error=str(exc))
            finally:
                self._generating = False
                try:
                    self.stop_btn.visible = False
                    self.stop_btn.update()
                except Exception as ex:
                    logger.debug("hide stop button failed: %s", ex)

        try:
            self.page.run_task(_run_chat)
        except Exception:
            _run_chat()

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
                except Exception as ex:
                    logger.debug("search message read failed: %s", ex)
            if query in text:
                try:
                    if hasattr(self.chat_list, "scroll_to"):
                        self.chat_list.scroll_to(delta=99999, duration=200)
                except Exception as ex:
                    logger.debug("search scroll failed: %s", ex)
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
            if hasattr(self, "_on_input_change"):
                self._on_input_change()
        except Exception:
            logger.debug("apply prompt template failed: %s", traceback.format_exc())
