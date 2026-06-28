import flet as ft
import threading
from prism.agent import create_agent


_agent = create_agent()
_send_lock = {}


def _on_input_change(self, text):
    pass


def _append(main_self, role, text, retry=False, retry_text="", placeholder=False):
    is_user = role == "你"
    align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
    bg = ft.Colors.PRIMARY_CONTAINER if is_user else ft.Colors.SURFACE
    text_color = ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE
    avatar = ft.Icon(ft.Icons.PERSON_ROUNDED if is_user else ft.Icons.SMART_TOY_ROUNDED, size=28, color=ft.Colors.ON_SURFACE)

    content = ft.Text(text, selectable=True, color=text_color)
    bubble = ft.Container(
        content=ft.Column([content], tight=True),
        bgcolor=bg,
        padding=ft.padding.symmetric(horizontal=14, vertical=8),
        border_radius=16,
    )

    row = ft.Row(
        [avatar, bubble] if not is_user else [bubble, avatar],
        alignment=align,
        spacing=6,
    )

    try:
        main_self.chat_list.controls.append(row)
        main_self.chat_list.update()
    except Exception:
        pass


def _send(self, text=None):
    if text is None:
        text = ""
    if not text or not text.strip():
        return
    if _send_lock.get(id(self)):
        return

    _send_lock[id(self)] = True
    self.input_field.disabled = True
    self.send_btn.visible = False
    self.stop_btn.visible = True
    self._set_status("PRISM 正在思考...", ft.Colors.AMBER_400)
    self._append_terminal(f">>> {text}")
    try:
        self._append("你", text)
    except Exception:
        pass

    full_reply = ""

    def _on_chunk(chunk: str):
        nonlocal full_reply
        full_reply += chunk

    def _do_chat():
        reply = ""
        try:
            reply = _agent.chat(text, on_stream=_on_chunk) or ""
        except Exception as e:
            reply = f"Error: {e}"
        if not full_reply:
            full_reply = reply or "(无回复)"

        def _finish():
            self._append("PRISM", full_reply)
            self._set_status("就绪")
            self.input_field.disabled = False
            self.send_btn.visible = True
            self.stop_btn.visible = False
            self.input_field.focus()
            _send_lock[id(self)] = False

        try:
            self.page.call_later(0, _finish)
        except Exception:
            _finish()

    t = threading.Thread(target=_do_chat, daemon=True)
    t.start()


def _format_time(self):
    import datetime
    return datetime.datetime.now().strftime("%H:%M")


def _markdown_to_ft(self, text):
    import re
    import markdown
    from flet import Markdown
    return Markdown(
        text,
        selectable=True,
        extension_set=markdown.extensions.extra(),
        on_tap_link=lambda e: None,
    )
