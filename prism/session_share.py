"""
PRISM Agent - 会话分享
会话导出为可分享链接/文件
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SHARE_DIR = Path.home() / ".prism" / "shares"
_SHARE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SharedSession:
    id: str
    session_id: str = ""
    title: str = ""
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "title": self.title,
            "messages": self.messages,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
        }


class SessionShare:
    def create(self, session_id: str, messages: List[Dict[str, Any]], title: str = "", ttl_hours: int = 24) -> SharedSession:
        share_id = f"share_{int(time.time())}_{session_id}"
        share = SharedSession(id=share_id, session_id=session_id, title=title, messages=messages, expires_at=time.time() + ttl_hours * 3600)
        try:
            (_SHARE_DIR / f"{share_id}.json").write_text(
                json.dumps(share.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return share

    def get(self, share_id: str) -> Optional[SharedSession]:
        path = _SHARE_DIR / f"{share_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            share = SharedSession(**data)
            if share.expires_at and share.expires_at < time.time():
                return None
            return share
        except Exception:
            return None

    def list_shares(self) -> List[Dict[str, Any]]:
        shares = []
        for share_file in _SHARE_DIR.glob("*.json"):
            try:
                data = json.loads(share_file.read_text(encoding="utf-8"))
                shares.append(data)
            except Exception:
                continue
        shares.sort(key=lambda x: x.get("created_at", 0))
        return shares[-100:]


session_share = SessionShare()
