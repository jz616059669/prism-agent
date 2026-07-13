"""
PRISM Agent - Prompt 缓存热键
常用 prompt 一键调用
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_HOTKEY_DIR = Path.home() / ".prism" / "hotkeys"
_HOTKEY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class PromptHotkey:
    name: str
    prompt: str = ""
    shortcut: str = ""
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "prompt": self.prompt,
            "shortcut": self.shortcut,
            "description": self.description,
        }


class PromptHotkeyStore:
    def __init__(self) -> None:
        self._hotkeys: Dict[str, PromptHotkey] = {}
        self._load()

    def _load(self) -> None:
        for hotkey_file in _HOTKEY_DIR.glob("*.json"):
            try:
                data = json.loads(hotkey_file.read_text(encoding="utf-8"))
                hotkey = PromptHotkey(**data)
                self._hotkeys[hotkey.name] = hotkey
            except Exception:
                continue

    def add(self, hotkey: PromptHotkey) -> PromptHotkey:
        self._hotkeys[hotkey.name] = hotkey
        self._save(hotkey)
        return hotkey

    def get(self, name: str) -> Optional[PromptHotkey]:
        return self._hotkeys.get(name)

    def list_hotkeys(self) -> List[Dict[str, Any]]:
        return [h.to_dict() for h in self._hotkeys.values()]

    def expand(self, shortcut: str) -> str:
        for hotkey in self._hotkeys.values():
            if hotkey.shortcut == shortcut and hotkey.prompt:
                return hotkey.prompt
        return shortcut

    def _save(self, hotkey: PromptHotkey) -> None:
        try:
            (_HOTKEY_DIR / f"{hotkey.name}.json").write_text(
                json.dumps(hotkey.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


prompt_hotkey_store = PromptHotkeyStore()
