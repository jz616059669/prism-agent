"""
PRISM Agent - 桌面端通知系统
系统通知 + 声音提醒
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_NOTIFY_DIR = Path.home() / ".prism" / "notifications"
_NOTIFY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Notification:
    id: str
    title: str = ""
    body: str = ""
    category: str = "info"
    sound: bool = False
    created_at: float = field(default_factory=lambda: __import__("time").time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "body": self.body,
            "category": self.category,
            "sound": self.sound,
            "created_at": self.created_at,
        }


class NotificationSystem:
    def __init__(self) -> None:
        self._history: List[Notification] = []
        self._ui_callback: Optional[Any] = None

    def set_ui_callback(self, callback: Any) -> None:
        self._ui_callback = callback

    def notify(self, title: str, body: str, category: str = "info", sound: bool = False) -> Notification:
        notification = Notification(id=f"notify_{int(__import__('time').time())}", title=title, body=body, category=category, sound=sound)
        self._history.append(notification)
        self._send(notification)
        self._save(notification)
        try:
            if self._ui_callback is not None:
                self._ui_callback(notification)
        except Exception:
            pass
        return notification

    def _send(self, notification: Notification) -> None:
        try:
            if os.name == "nt":
                try:
                    from win10toast import ToastNotifier
                    if not hasattr(self, "_toast_notifier") or self._toast_notifier is None:
                        self._toast_notifier = ToastNotifier()
                    self._toast_notifier.show_toast(notification.title, notification.body, duration=5, threaded=True)
                    return
                except Exception:
                    pass
                if notification.sound:
                    try:
                        import winsound
                        winsound.MessageBeep(winsound.MB_ICONASTERISK)
                    except Exception:
                        pass
                return
            # 非 Windows 平台 fallback：打印到 stdout / 使用 plyer（如果可用）
            try:
                from plyer import notification as plyer_notify
                plyer_notify.notify(title=notification.title, message=notification.body, timeout=5)
            except Exception:
                logger.info("notification: %s | %s", notification.title, notification.body)
        except Exception:
            pass

    def _save(self, notification: Notification) -> None:
        try:
            with (_NOTIFY_DIR / "history.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(notification.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [n.to_dict() for n in self._history[-limit:]]


notification_system = NotificationSystem()
