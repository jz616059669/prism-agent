"""
PRISM Agent - 多窗口状态同步
桌面端多个窗口实时同步
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SYNC_DIR = Path.home() / ".prism" / "window_sync"
_SYNC_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class WindowState:
    window_id: str
    session_id: str = ""
    active_tab: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "window_id": self.window_id,
            "session_id": self.session_id,
            "active_tab": self.active_tab,
            "messages": self.messages,
            "updated_at": self.updated_at,
        }


class WindowSync:
    def __init__(self) -> None:
        self._states: Dict[str, WindowState] = {}
        self._load()

    def _load(self) -> None:
        for state_file in _SYNC_DIR.glob("*.json"):
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                state = WindowState(**data)
                self._states[state.window_id] = state
            except Exception:
                continue

    def update(self, state: WindowState) -> WindowState:
        self._states[state.window_id] = state
        self._save(state)
        return state

    def get(self, window_id: str) -> Optional[WindowState]:
        return self._states.get(window_id)

    def list_windows(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._states.values()]

    def _save(self, state: WindowState) -> None:
        try:
            (_SYNC_DIR / f"{state.window_id}.json").write_text(
                json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


window_sync = WindowSync()
