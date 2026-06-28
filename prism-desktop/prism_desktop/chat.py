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
    text_color = ft.Colors.ON_PRIMARY_CONTAINER if is_user else ft.Colors.ON_SURFACE

    try:
        main_self.chat_list.controls.append(
            ft.Row(
                [ft.Text(text, selectable=True, color=text_color, expand=not is_user)],
                alignment=align,
                expand=True,
            )
        )
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
    # keep input enabled during reply
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

    def _finish(reply_text=None):
        if watchdog["timer"]:
            watchdog["timer"].cancel()
            watchdog["timer"] = None
        display = reply_text if reply_text is not None else (full_reply or "(无回复)")
        try:
            self._append("PRISM", display)
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
        reply = ""
        try:
            reply = _agent.chat(text, on_stream=_on_chunk) or ""
        except Exception as e:
            reply = f"Error: {e}"
        try:
            self.page.call_later(0, lambda: _finish(reply))
        except Exception:
            _finish(reply)

    def _watchdog():
        if _send_lock.get(id(self)):
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
