"""
PRISM Agent - 定时提醒
基于 cron 的提醒系统，支持自然语言
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REMINDER_DIR = Path.home() / ".prism" / "reminders"
_REMINDER_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Reminder:
    id: str
    text: str = ""
    cron: str = ""
    next_ts: float = 0.0
    enabled: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "cron": self.cron,
            "next_ts": self.next_ts,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


class ReminderStore:
    def __init__(self) -> None:
        self._reminders: Dict[str, Reminder] = {}
        self._load()

    def _load(self) -> None:
        for reminder_file in _REMINDER_DIR.glob("*.json"):
            try:
                data = json.loads(reminder_file.read_text(encoding="utf-8"))
                reminder = Reminder(**data)
                self._reminders[reminder.id] = reminder
            except Exception:
                continue

    def add(self, reminder: Reminder) -> Reminder:
        self._reminders[reminder.id] = reminder
        self._save(reminder)
        return reminder

    def get(self, reminder_id: str) -> Optional[Reminder]:
        return self._reminders.get(reminder_id)

    def list_reminders(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._reminders.values()]

    def remove(self, reminder_id: str) -> bool:
        if reminder_id not in self._reminders:
            return False
        del self._reminders[reminder_id]
        try:
            (_REMINDER_DIR / f"{reminder_id}.json").unlink()
        except Exception:
            pass
        return True

    def due(self) -> List[Reminder]:
        now = time.time()
        return [r for r in self._reminders.values() if r.enabled and r.next_ts and r.next_ts <= now]

    def _save(self, reminder: Reminder) -> None:
        try:
            (_REMINDER_DIR / f"{reminder.id}.json").write_text(
                json.dumps(reminder.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


reminder_store = ReminderStore()
