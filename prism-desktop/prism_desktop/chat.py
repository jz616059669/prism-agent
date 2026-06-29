import flet as ft
import threading
from prism.agent import create_agent


_agent = create_agent()
_send_lock = {}
_streaming_indicator = None


def _on_input_change(self, text):
    pass


def _append(main_self, role, text, retry=False, retry_text="", placeholder=False):
    is_user = role == "你"
    align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
    text_color = ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE
    import datetime
    timestamp = datetime.datetime.now().strftime("%H:%M")

    try:
        if is_user:
            bubble = ft.Container(
                content=ft.Text(text, selectable=True, color=text_color, size=14),
                bgcolor=ft.Colors.PRIMARY_CONTAINER,
                border_radius=14,
                padding=ft.Padding(10, 8, 10, 8),
                shadow=ft.BoxShadow(blur_radius=4, spread_radius=0, color=ft.Colors.with_opacity(0.15, ft.Colors.PRIMARY)),
            )
            content_widget = ft.Column(
                [
                    bubble,
                    ft.Text(timestamp, size=10, color=ft.Colors.ON_SURFACE_VARIANT, text_align=ft.TextAlign.END),
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.END,
            )
        else:
            is_error = text.startswith("Error:") or text.startswith("请求超时")
            bg = ft.Colors.ERROR_CONTAINER if is_error else ft.Colors.SURFACE_CONTAINER
            text_c = ft.Colors.ON_ERROR_CONTAINER if is_error else text_color
            bubble = ft.Container(
                content=ft.Text(text, selectable=True, color=text_c, size=14),
                bgcolor=bg,
                border_radius=14,
                padding=ft.Padding(10, 8, 10, 8),
                shadow=ft.BoxShadow(blur_radius=3, spread_radius=0, color=ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE)),
            )
            content_widget = ft.Column(
                [
                    bubble,
                    ft.Text(timestamp, size=10, color=ft.Colors.ON_SURFACE_VARIANT),
                ],
                spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.START,
            )
        message_row = ft.Row(
            [content_widget],
            alignment=align,
            expand=True,
            opacity=0,
            animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        )
        main_self.chat_list.controls.append(message_row)
        message_row.opacity = 1
        message_row.update()
        
        # Add retry button for error messages
        if not is_user and is_error and retry_text:
            retry_btn = ft.TextButton(
                "重试",
                icon=ft.Icons.REFRESH_ROUNDED,
                style=ft.ButtonStyle(color=ft.Colors.ERROR),
                on_click=lambda e, t=retry_text: main_self._send(t),
            )
            retry_row = ft.Row(
                [retry_btn],
                alignment=ft.MainAxisAlignment.START,
                expand=True,
                opacity=0,
                animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
            )
            main_self.chat_list.controls.append(retry_row)
            retry_row.opacity = 1
            retry_row.update()
        
        main_self.chat_list.update()
    except Exception:
        pass


def _show_streaming_indicator(main_self):
    global _streaming_indicator
    try:
        _streaming_indicator = ft.Row(
            [ft.Text("PRISM 正在输入...", size=12, color=ft.Colors.ON_SURFACE_VARIANT, italic=True)],
            alignment=ft.MainAxisAlignment.START,
        )
        main_self.chat_list.controls.append(_streaming_indicator)
        main_self.chat_list.update()
    except Exception:
        pass


def _hide_streaming_indicator(main_self):
    global _streaming_indicator
    try:
        if _streaming_indicator and _streaming_indicator in main_self.chat_list.controls:
            main_self.chat_list.controls.remove(_streaming_indicator)
            main_self.chat_list.update()
    except Exception:
        pass
    _streaming_indicator = None


def _send(self, text=None):
    if text is None:
        text = ""
    if not text or not text.strip():
        return
    if _send_lock.get(id(self)):
        return

    _send_lock[id(self)] = True
    self.send_btn.visible = False
    self.stop_btn.visible = True
    self._set_status("PRISM 正在思考...", ft.Colors.AMBER_400)
    self._append_terminal(f">>> {text}")
    try:
        self._append("你", text)
    except Exception:
        pass

    full_reply = ""
    watchdog = {"timer": None}

    def _on_chunk(chunk: str):
        nonlocal full_reply
        full_reply += chunk

    def _finish(reply_text=None, retry_text=""):
        if watchdog["timer"]:
            watchdog["timer"].cancel()
            watchdog["timer"] = None
        _hide_streaming_indicator(self)
        display = reply_text if reply_text is not None else (full_reply or "(无回复)")
        is_error = display.startswith("Error:") or display.startswith("请求超时")
        try:
            self._append("PRISM", display, retry_text=retry_text if is_error else "")
        except Exception:
            pass
        self._set_status("就绪")
        self.send_btn.visible = True
        self.stop_btn.visible = False
        try:
            self.input_field.focus()
        except Exception:
            pass
        _send_lock[id(self)] = False

    def _do_chat():
        _show_streaming_indicator(self)
        reply = ""
        try:
            reply = _agent.chat(text, on_stream=_on_chunk) or ""
        except Exception as e:
            reply = f"Error: {e}"
        try:
            self.page.call_later(0, lambda r=reply: _finish(r, retry_text=text))
        except Exception:
            _finish(reply, retry_text=text)

    def _watchdog():
        if _send_lock.get(id(self)):
            _hide_streaming_indicator(self)
            _finish("请求超时（60秒），请检查网络或稍后重试。")

    watchdog["timer"] = threading.Timer(60, _watchdog)
    watchdog["timer"].daemon = True
    watchdog["timer"].start()

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
