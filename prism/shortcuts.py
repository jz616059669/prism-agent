"""
PRISM Agent - 快捷键系统
桌面端全局快捷键映射
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SHORTCUT_DIR = Path.home() / ".prism" / "shortcuts"
_SHORTCUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Shortcut:
    name: str
    keys: str = ""
    action: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "keys": self.keys,
            "action": self.action,
            "description": self.description,
        }


class ShortcutStore:
    def __init__(self) -> None:
        self._shortcuts: Dict[str, Shortcut] = {}
        self._load_defaults()
        self._load()

    def _load_defaults(self) -> None:
        self._shortcuts = {
            "send": Shortcut(name="send", keys="Enter", action="send_message", description="发送消息"),
            "new_line": Shortcut(name="new_line", keys="Shift+Enter", action="new_line", description="换行"),
            "clear": Shortcut(name="clear", keys="Ctrl+L", action="clear_chat", description="清空对话"),
            "settings": Shortcut(name="settings", keys="Ctrl+,", action="open_settings", description="打开设置"),
        }

    def _load(self) -> None:
        for shortcut_file in _SHORTCUT_DIR.glob("*.json"):
            try:
                data = json.loads(shortcut_file.read_text(encoding="utf-8"))
                shortcut = Shortcut(**data)
                self._shortcuts[shortcut.name] = shortcut
            except Exception:
                continue

    def get(self, name: str) -> Optional[Shortcut]:
        return self._shortcuts.get(name)

    def list_shortcuts(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._shortcuts.values()]

    def add(self, shortcut: Shortcut) -> Shortcut:
        self._shortcuts[shortcut.name] = shortcut
        try:
            (_SHORTCUT_DIR / f"{shortcut.name}.json").write_text(
                json.dumps(shortcut.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return shortcut


shortcut_store = ShortcutStore()
