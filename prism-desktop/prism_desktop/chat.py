"""PRISM Desktop - 聊天与消息 UI"""
from __future__ import annotations

import datetime
import os
from pathlib import Path
import json
import threading
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
        try:
            return [ft.Markdown(text, selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB, on_tap_link=lambda e: None)]
        except Exception:
            return [ft.Text(text, selectable=True, color=text_color)]

    def _append(self, role: str, text: str, retry: bool = False, retry_text: str = "", placeholder: bool = False, images=None):
        def _apply():
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
                    opacity=0,
                    animate_opacity=ft.Animation(duration=180, curve=ft.AnimationCurve.EASE_OUT),
                )
                copy_btn = ft.IconButton(
                    icon=ft.Icons.COPY_ROUNDED,
                    tooltip="复制",
                    icon_size=14,
                    icon_color=ft.Colors.ON_SURFACE_VARIANT,
                    bgcolor=ft.Colors.with_opacity(0, ft.Colors.TRANSPARENT),
                    style=ft.ButtonStyle(shape=ft.CircleBorder(), overlay_color=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE_VARIANT)),
                    on_click=lambda e, t=text: self._copy_to_clipboard(t) if hasattr(self, "_copy_to_clipboard") else None,
                )
                message_widget = ft.Stack(
                    [
                        message_widget,
                        ft.Container(
                            content=copy_btn,
                            alignment=ft.alignment.top_right,
                            padding=ft.Padding(6, 6, 6, 6),
                        ),
                    ],
                    height=None,
                )
                self.chat_list.controls.append(message_widget)
                message_widget.opacity = 1
                try:
                    self.chat_list.update()
                except Exception:
                    logger.debug("chat_list update failed: %s", traceback.format_exc())
            except Exception:
                logger.debug("append message failed: %s", traceback.format_exc())
                try:
                    self._append_terminal(f"[CHAT ERROR] {role}: {text[:200]}")
                except Exception as ex:
                    logger.debug("append message fallback failed: %s", ex)
        try:
            self._run_on_ui(_apply)
        except Exception:
            logger.debug("run_on_ui append failed", exc_info=True)

    def _apply_input_update(self):
        def _ui():
            try:
                if hasattr(self, "input_count") and self.input_count and getattr(self.input_count, "page", None):
                    count = len(self.input_field.value or "")
                    self.input_count.value = f"{count} 字"
                    self.input_count.update()
                if hasattr(self, "send_btn") and self.send_btn:
                    self.send_btn.disabled = not (self.input_field.value or "").strip()
                    if getattr(self.send_btn, "page", None):
                        self.send_btn.update()
            except Exception:
                logger.debug("apply input update failed", exc_info=True)
        try:
            if hasattr(self, "_run_on_ui"):
                self._run_on_ui(_ui)
            else:
                _ui()
        except Exception:
            logger.debug("apply input update failed", exc_info=True)

    def _clear_chat(self):
        def _apply():
            try:
                self.chat_list.controls.clear()
                self.chat_list.controls.append(self._chat_placeholder)
                try:
                    self.chat_list.update()
                except Exception:
                    logger.debug("clear chat update failed", exc_info=True)
            except Exception:
                logger.debug("clear chat failed: %s", traceback.format_exc())
        try:
            self._run_on_ui(_apply)
        except Exception:
            logger.debug("clear chat run_on_ui failed", exc_info=True)
        self.input_field.value = ""
        self.input_field.focus()
        self._update_input_count()
        self._set_status("已清屏")

    def _send(self, retry_text: str = ""):
        text = retry_text or (self.input_field.value or "").strip()
        images = list(getattr(self, "_pending_images", []) or [])
        if not text and not images:
            return
        if text.startswith("/"):
            cmd = text.lower()
            if cmd in ("/summarize", "/compact"):
                self._handle_compact_command(cmd)
            elif cmd == "/rollback":
                self._handle_rollback_command()
            else:
                self._append("PRISM", "未知命令。支持: /summarize, /compact, /rollback")
            return
        if not getattr(self, "agent", None):
            self._append("PRISM", "Error: agent 未初始化，请检查配置并保存后重试。")
            self._log_to_file("warning", "send_blocked", reason="agent is None")
            return
        self.input_field.value = ""
        try:
            self.input_field.update()
        except Exception:
            logger.debug("input field clear failed", exc_info=True)
        self._generating = True
        self.stop_btn.visible = True
        try:
            self.stop_btn.update()
        except Exception:
            logger.debug("show stop button failed", exc_info=True)
        if images:
            try:
                if hasattr(self, "_clear_pending_images"):
                    self._clear_pending_images()
            except Exception:
                pass
            display_text = text if text else "图片"
            self._append("你", display_text, images=images)
            multimodal_content = self._build_multimodal_content(text, images)
        else:
            self._append("你", text)
            multimodal_content = text


        stream_widget = None
        stream_text = ""
        _last_update = [0.0]
        _stream_content_ref = None

        def _throttled_update(w, value: str):
            nonlocal _stream_content_ref
            now = __import__("time").time()
            target = _stream_content_ref
            if target is None:
                target = w.content.controls[2]
            if now - _last_update[0] >= 0.1 or len(value) - len((target.value or "")) >= 24:
                try:
                    target.value = value
                    w.update()
                    _last_update[0] = now
                except Exception:
                    logger.debug("stream chunk update failed: %s", traceback.format_exc())

        def _ensure_stream_widget() -> ft.Container:
            nonlocal stream_widget, _stream_content_ref
            if stream_widget is None:
                role_text = ft.Text("PRISM", size=11, color=ft.Colors.ON_SURFACE_VARIANT, weight=ft.FontWeight.W_500)
                timestamp = datetime.now().strftime("%H:%M")
                time_text = ft.Text(timestamp, size=11, color=ft.Colors.ON_SURFACE_VARIANT, opacity=0.8)
                stream_content = ft.Text("", selectable=True, color=ft.Colors.ON_SURFACE, expand=True)
                _stream_content_ref = stream_content
                row = ft.Row(
                    [role_text, ft.Container(expand=True), time_text],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                )
                stream_widget = ft.Container(
                    content=ft.Column(
                        [row, ft.Container(height=4), stream_content],
                        tight=False,
                        spacing=0,
                        horizontal_alignment=ft.MainAxisAlignment.START,
                    ),
                    padding=ft.Padding(14, 10, 14, 10),
                    bgcolor=ft.Colors.SURFACE_CONTAINER,
                    opacity=0,
                    animate_opacity=ft.Animation(duration=120, curve=ft.AnimationCurve.EASE_OUT),
                )
                self.chat_list.controls.append(stream_widget)
                stream_widget.opacity = 1
                try:
                    self.chat_list.update()
                except Exception:
                    logger.debug("chat_list update failed: %s", traceback.format_exc())
            return stream_widget

        def _stream_chunk(c: str):
            nonlocal stream_text
            stream_text += c
            w = _ensure_stream_widget()
            try:
                def _apply_chunk():
                    try:
                        _throttled_update(w, stream_text)
                    except Exception:
                        logger.debug("stream chunk update failed", exc_info=True)
                if hasattr(self, "_run_on_ui"):
                    self._run_on_ui(_apply_chunk)
                else:
                    _apply_chunk()
            except Exception:
                logger.debug("stream chunk update failed", exc_info=True)
            try:
                if hasattr(self, "_chunk_count"):
                    self._chunk_count = getattr(self, "_chunk_count", 0) + 1
            except Exception:
                pass

        def _run_chat() -> None:
            nonlocal stream_widget, stream_text
            try:
                agent_model = getattr(self.agent, 'model', None)
                agent_provider = getattr(self.agent, 'provider', None)
                logger.info("run_chat start model=%s provider=%s messages=%d system_prompt_len=%d", 
                           agent_model, agent_provider, len(getattr(self.agent, 'messages', []) or []),
                           len(getattr(self.agent, 'system_prompt', '') or ''))
                try:
                    api_msgs = [{"role": m.role, "content": (m.content or "")} for m in getattr(self.agent, 'messages', [])]
                    logger.info("api_messages=%s", api_msgs)
                except Exception:
                    pass
                try:
                    import json as _json
                    with open(r'C:\Users\zd\.prism\debug_api_messages.json', 'w', encoding='utf-8') as _f:
                        _json.dump([{"role": m.role, "content": m.content} for m in getattr(self.agent, 'messages', [])], _f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
                self._log_to_file("info", "stream_start", text=text, model=getattr(self.agent, "model", "unknown"))
                result = self.agent.chat(
                    multimodal_content,
                    on_stream=lambda c: _stream_chunk(c) if getattr(self, "_generating", False) else None,
                    stop_callback=lambda: not getattr(self, "_generating", False),
                )
                logger.info("chat result type=%s preview=%s len=%d", type(result).__name__, str(result)[:200], len(str(result)))
                if not getattr(self, "_generating", False):
                    self._log_to_file("info", "stream_stopped", chunks=getattr(self, "_chunk_count", 0))
                def _finalize():
                    # 优先以流式累积文本为准，避免 provider 返回 content 被截断/异常
                    text = stream_text
                    if not text and isinstance(result, dict):
                        text = result.get('content') or ''
                    if not text and isinstance(result, str):
                        text = result or ''
                    if not text:
                        text = ' '
                    try:
                        import json as _json2
                        _finalize_debug = {
                            'stream_text_len': len(stream_text or ''),
                            'stream_text_preview': (stream_text or '')[:80],
                            'result_type': type(result).__name__,
                            'result_preview': str(result)[:120] if result is not None else None,
                            'final_text_len': len(text),
                            'final_text_preview': text[:80],
                            'generating': getattr(self, '_generating', None),
                        }
                        with open(r'C:\Users\zd\.prism\debug_api_messages_finalize.json', 'w', encoding='utf-8') as _f2:
                            _json2.dump(_finalize_debug, _f2, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                    self._append("PRISM", text)
                try:
                    page = getattr(self, "page", None)
                    if page is not None and hasattr(page, "run_task"):
                        page.run_task(lambda: _finalize())
                    else:
                        _finalize()
                except Exception:
                    _finalize()
            except Exception as exc:
                logger.error("send exception: %s", exc, exc_info=True)
                try:
                    page = getattr(self, "page", None)
                    if page is not None and hasattr(page, "run_task"):
                        page.run_task(lambda: self._append("PRISM", f"Error: {exc}"))
                    else:
                        self._append("PRISM", f"Error: {exc}")
                except Exception:
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
            threading.Thread(target=_run_chat, daemon=True).start()
        except Exception:
            _run_chat()

    def _stop_send(self):
        self._generating = False

    def _search_messages(self, query: str, direction: int = 1):
        if not query:
            self._clear_search_highlights()
            return
        items = getattr(self.chat_list, "controls", [])
        matches = []
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
                matches.append(idx)
        if not matches:
            self._clear_search_highlights()
            return
        if not hasattr(self, "_search_index"):
            self._search_index = -1
        if direction > 0:
            self._search_index = (self._search_index + 1) % len(matches)
        else:
            self._search_index = (self._search_index - 1) % len(matches)
        target = matches[self._search_index]
        self._clear_search_highlights()
        try:
            target_item = items[target]
            if hasattr(target_item, "bgcolor"):
                target_item.bgcolor = ft.Colors.with_opacity(0.25, ft.Colors.PRIMARY)
                target_item.update()
            if hasattr(self.chat_list, "scroll_to") and hasattr(self.chat_list, "page"):
                async def _do_scroll():
                    await self.chat_list.scroll_to(offset=target_item.top or 0, duration=200)
                self.chat_list.page.run_task(_do_scroll)
        except Exception as ex:
            logger.debug("search scroll failed: %s", ex)
        self._search_query = query
        self._search_matches = matches

    def _jump_to_next_match(self, query: str):
        self._search_messages(query or getattr(self, "_search_query", ""), direction=1)

    def _prev_match(self, query: str):
        self._search_messages(query or getattr(self, "_search_query", ""), direction=-1)

    def _clear_search_highlights(self):
        try:
            for item in getattr(self.chat_list, "controls", []):
                if hasattr(item, "bgcolor"):
                    item.bgcolor = None
                    item.update()
        except Exception:
            pass
        self._search_index = -1
        self._search_matches = []
        self._search_query = ""

    def _export_current_chat(self):
        try:
            items = getattr(self.chat_list, "controls", [])
            lines = ["# PRISM Chat Export", ""]
            for item in items:
                text = ""
                role = ""
                if hasattr(item, "content") and hasattr(item.content, "content"):
                    try:
                        controls = item.content.content.controls
                        if controls:
                            role = getattr(controls[0], "value", "") or ""
                            for ctrl in controls:
                                if hasattr(ctrl, "value"):
                                    text += str(ctrl.value)
                    except Exception:
                        pass
                if not text.strip():
                    continue
                label = role.strip() or "message"
                lines.append(f"## {label}")
                lines.append(text.strip())
                lines.append("")
            path = os.path.join(str(Path.home()), ".prism", f"chat_export_{int(__import__('time').time())}.md")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            self._set_status(f"已导出: {path}", ft.Colors.GREEN_400)
            self._append_terminal(f"chat exported: {path}")
        except Exception as exc:
            self._log_error("export chat failed", exc)
            self._set_status("导出失败", ft.Colors.RED_400)

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

    def _handle_compact_command(self, cmd: str) -> None:
        try:
            if cmd == "/compact":
                messages = []
                try:
                    if hasattr(self, "agent") and self.agent:
                        messages = [
                            {"role": getattr(m, "role", ""), "content": getattr(m, "content", "") or ""}
                            for m in getattr(self.agent, "messages", []) or []
                        ]
                except Exception:
                    messages = []
                if not messages:
                    self._append("PRISM", "当前没有可压缩的对话上下文。")
                    return
                try:
                    from prism.context_compactor import context_compactor
                    summary = context_compactor.compact(getattr(self, "session_id", "default"), messages)
                    text = summary.summary or "（摘要为空）"
                except Exception:
                    text = "压缩模块暂不可用，请稍后重试。"
                self._append("PRISM", f"上下文摘要：\n{text}")
                self._set_status("上下文已压缩", ft.Colors.GREEN_400)
            elif cmd == "/summarize":
                try:
                    from prism.context_compactor import context_compactor
                    messages = []
                    try:
                        if hasattr(self, "agent") and self.agent:
                            messages = [
                                {"role": getattr(m, "role", ""), "content": getattr(m, "content", "") or ""}
                                for m in getattr(self.agent, "messages", []) or []
                            ]
                    except Exception:
                        messages = []
                    summary = context_compactor.compact(getattr(self, "session_id", "default"), messages or [])
                    text = summary.summary or "（摘要为空）"
                except Exception:
                    text = "摘要模块暂不可用，请稍后重试。"
                self._append("PRISM", f"对话摘要：\n{text}")
                self._set_status("摘要完成", ft.Colors.GREEN_400)
        except Exception as exc:
            self._append("PRISM", f"命令执行失败: {exc}")
            self._log_error("compact command", exc)

    def _handle_rollback_command(self) -> None:
        try:
            self._append("PRISM", "rollback 尚未实现")
        except Exception as exc:
            self._append("PRISM", f"命令执行失败: {exc}")
            self._log_error("rollback command", exc)
