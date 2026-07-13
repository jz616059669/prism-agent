"""
PRISM Agent - 消息撤回/编辑
撤回已发送消息，重新生成
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MSG_DIR = Path.home() / ".prism" / "messages"
_MSG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Message:
    id: str
    role: str = "user"
    content: str = ""
    session_id: str = ""
    created_at: float = field(default_factory=time.time)
    edited_at: float = 0.0
    retracted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "edited_at": self.edited_at,
            "retracted": self.retracted,
        }


class MessageStore:
    def __init__(self) -> None:
        self._messages: Dict[str, Message] = {}
        self._load()

    def _load(self) -> None:
        for msg_file in _MSG_DIR.glob("*.json"):
            try:
                data = json.loads(msg_file.read_text(encoding="utf-8"))
                msg = Message(**data)
                self._messages[msg.id] = msg
            except Exception:
                continue

    def add(self, message: Message) -> Message:
        self._messages[message.id] = message
        self._save(message)
        return message

    def edit(self, message_id: str, content: str) -> Optional[Message]:
        msg = self._messages.get(message_id)
        if not msg:
            return None
        msg.content = content
        msg.edited_at = time.time()
        self._save(msg)
        return msg

    def retract(self, message_id: str) -> Optional[Message]:
        msg = self._messages.get(message_id)
        if not msg:
            return None
        msg.retracted = True
        msg.content = ""
        self._save(msg)
        return msg

    def history(self, session_id: str, limit: int = 200) -> List[Dict[str, Any]]:
        items = [msg for msg in self._messages.values() if msg.session_id == session_id]
        items.sort(key=lambda m: m.created_at)
        return [m.to_dict() for m in items[-limit:]]

    def _save(self, message: Message) -> None:
        try:
            (_MSG_DIR / f"{message.id}.json").write_text(
                json.dumps(message.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


message_store = MessageStore()
