"""
PRISM Agent - 实时多人协作
本地 session 共享 + 文件锁，多窗口同源状态同步
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_COLLAB_DIR = Path.home() / ".prism" / "collab"
_COLLAB_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CollabSession:
    id: str
    name: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    owner: str = ""
    locked_by: str = ""
    locked_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "messages": self.messages,
            "owner": self.owner,
            "locked_by": self.locked_by,
            "locked_at": self.locked_at,
        }


class CollabStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, CollabSession] = {}
        self._load()

    def _load(self) -> None:
        for session_file in _COLLAB_DIR.glob("*.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                session = CollabSession(**data)
                self._sessions[session.id] = session
            except Exception:
                continue

    def _save(self, session: CollabSession) -> None:
        try:
            (_COLLAB_DIR / f"{session.id}.json").write_text(
                json.dumps(session.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def create(self, session: CollabSession) -> CollabSession:
        self._sessions[session.id] = session
        self._save(session)
        return session

    def get(self, session_id: str) -> Optional[CollabSession]:
        return self._sessions.get(session_id)

    def append_message(self, session_id: str, message: Dict[str, Any]) -> Optional[CollabSession]:
        session = self._sessions.get(session_id)
        if not session:
            return None
        session.messages.append(message)
        self._save(session)
        return session

    def list_sessions(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._sessions.values()]


collab_store = CollabStore()
