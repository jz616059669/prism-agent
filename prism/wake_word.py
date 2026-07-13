"""
PRISM Agent - 语音唤醒
本地唤醒词检测，免手动输入
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_WAKE_DIR = Path.home() / ".prism" / "wake"
_WAKE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class WakeWord:
    name: str
    phrase: str = ""
    enabled: bool = True
    sensitivity: float = 0.7

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "phrase": self.phrase,
            "enabled": self.enabled,
            "sensitivity": self.sensitivity,
        }


class WakeWordStore:
    def __init__(self) -> None:
        self._words: Dict[str, WakeWord] = {}
        self._load()

    def _load(self) -> None:
        for word_file in _WAKE_DIR.glob("*.json"):
            try:
                data = json.loads(word_file.read_text(encoding="utf-8"))
                word = WakeWord(**data)
                self._words[word.name] = word
            except Exception:
                continue

    def add(self, word: WakeWord) -> WakeWord:
        self._words[word.name] = word
        self._save(word)
        return word

    def get(self, name: str) -> Optional[WakeWord]:
        return self._words.get(name)

    def list_words(self) -> List[Dict[str, Any]]:
        return [w.to_dict() for w in self._words.values()]

    def detect(self, text: str) -> Optional[WakeWord]:
        t = (text or "").lower()
        for word in self._words.values():
            if word.enabled and word.phrase and word.phrase.lower() in t:
                return word
        return None

    def _save(self, word: WakeWord) -> None:
        try:
            (_WAKE_DIR / f"{word.name}.json").write_text(
                json.dumps(word.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


wake_word_store = WakeWordStore()
