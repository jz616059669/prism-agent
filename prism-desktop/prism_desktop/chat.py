"""PRISM Desktop - 聊天面板逻辑"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import flet as ft
import markdown
import re

if TYPE_CHECKING:
    from prism_desktop.main import PrismDesktop


def _format_time(self: PrismDesktop) -> str:
    return datetime.now().strftime("%m-%d %H:%M")


def _markdown_to_ft(self: PrismDesktop, text: str):
    try:
        rendered = markdown.markdown(text, extensions=["fenced_code", "tables"])
    except Exception:
        rendered = text
    return ft.Markdown(
        rendered,
        extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
        expand=True,
        selectable=True,
        on_tap_link=lambda e: None,
    )


def _append(
    self: PrismDesktop,
    role: str,
    text: str,
    retry: bool = False,
    retry_text: str = "",
    placeholder: bool = False,
):
    is_user = role == "你"
    align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
    bg = ft.Colors.PRIMARY_CONTAINER if is_user else ft.Colors.SURFACE

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

    actions = [
        ft.Text(_format_time(self), size=9, color=ft.Colors.ON_SURFACE),
        ft.TextButton("复制渲染", on_click=_copy),
        ft.TextButton("复制原文", on_click=_copy_raw),
        ft.TextButton("删除", on_click=_delete),
    ]
    if retry and retry_text:
        def _retry(_):
            try:
                self.input_field.value = retry_text
                self.input_field.disabled = False
                self.input_field.focus()
                self.input_field.update()
                _send(self)
            except Exception:
                pass
        actions.insert(2, ft.TextButton("重发", on_click=_retry))

    if placeholder:
        actions = [ft.Text(_format_time(self), size=9, color=ft.Colors.ON_SURFACE)]

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
            ft.TextButton(
                f"复制代码块 {idx+1}",
                on_click=_copy_code(),
                style=ft.ButtonStyle(padding=4),
            )
        )

    action_row = ft.Row(actions, spacing=8)
    if code_copy_buttons:
        action_row.controls.extend(code_copy_buttons)

    content = ft.Column(
        [
            ft.Text(role, size=11, color=ft.Colors.ON_SURFACE, weight=ft.FontWeight.BOLD),
            _markdown_to_ft(self, text),
            action_row,
        ],
        tight=True,
    )

    container_wrapper = ft.Container(
        content=content,
        bgcolor=bg,
        padding=10,
        border_radius=16,
        width=max(300, int(self.page.width * 0.7)),
        on_long_press=_on_right_click,
    )

    self.chat_list.controls.append(
        ft.Column(
            [container_wrapper],
            alignment=align,
            horizontal_alignment=align,
        )
    )
    max_chat_items = 200
    if len(self.chat_list.controls) > max_chat_items:
        self.chat_list.controls = self.chat_list.controls[-max_chat_items:]
    self.chat_list.scroll_to(offset=-1, duration=150)
    self.chat_list.update()
    return container_wrapper


def _clear_chat(self: PrismDesktop):
    self.chat_list.controls.clear()
    self.chat_list.update()
    self._append_terminal("chat cleared")


def _show_message_menu(self: PrismDesktop, e, target, message_text: str):
    pass


def _on_input_change(self: PrismDesktop):
    try:
        text = self.input_field.value or ""
        self.input_count.value = f"{len(text)} 字"
        self.input_count.update()
    except Exception:
        pass


def _send(self: PrismDesktop):
    try:
        text = self.input_field.value.strip()
    except Exception as e:
        self._append_terminal(f"send error read input: {e}")
        return

    if not text:
        return

    try:
        self._append_terminal(f">>> {text}")
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
        full_reply = ""

        def _update_placeholder(container, txt: str, final: bool = False):
            try:
                container.content.controls[1] = _markdown_to_ft(self, txt)
                if final:
                    container.content.controls[0].color = ft.Colors.ON_SURFACE_VARIANT
                    container.bgcolor = ft.Colors.SURFACE
                container.update()
                self.chat_list.scroll_to(offset=-1, duration=0)
            except Exception as ex:
                self._append_terminal(f"update placeholder error: {ex}")

        def _on_chunk(chunk: str):
            nonlocal full_reply
            full_reply += chunk
            try:
                self.page.call_later(0, lambda c=placeholder, t=full_reply: _update_placeholder(c, t))
            except Exception:
                _update_placeholder(placeholder, full_reply)

        def _do_chat():
            reply = ""
            try:
                reply = self.agent.chat(text, on_stream=_on_chunk) or ""
            except Exception as e:
                reply = f"Error: {e}"
                try:
                    self.page.call_later(0, lambda: self._append_terminal(f"chat error: {e}"))
                except Exception:
                    self._append_terminal(f"chat error: {e}")

            def _finish():
                if not full_reply:
                    full_reply = reply or "(无回复)"
                    _update_placeholder(placeholder, full_reply, final=True)
                self._set_status("就绪")
                self.input_field.disabled = False
                self.send_btn.visible = True
                self.stop_btn.visible = False
                self.send_btn.update()
                self.stop_btn.update()
                self._append_terminal(f"<<< {full_reply[:120]}")
                try:
                    self.input_field.focus()
                except Exception:
                    pass
                self.page.update()

            try:
                self.page.call_later(0, _finish)
            except Exception:
                _finish()

        import threading
        t = threading.Thread(target=_do_chat, daemon=True)
        t.start()
    except Exception as e:
        self._append_terminal(f"send error: {e}")
        self.input_field.disabled = False
        self.send_btn.visible = True
        self.stop_btn.visible = False
        self.input_field.update()
        self.send_btn.update()
        self.stop_btn.update()
