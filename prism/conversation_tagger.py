"""
PRISM Agent - 对话标签/收藏
标记重要对话
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TAG_DIR = Path.home() / ".prism" / "tags"
_TAG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ConversationTag:
    session_id: str
    tag: str = ""
    favorite: bool = False
    note: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "tag": self.tag,
            "favorite": self.favorite,
            "note": self.note,
            "created_at": self.created_at,
        }


class ConversationTagger:
    def __init__(self) -> None:
        self._tags: Dict[str, ConversationTag] = {}
        self._load()

    def _load(self) -> None:
        for tag_file in _TAG_DIR.glob("*.json"):
            try:
                data = json.loads(tag_file.read_text(encoding="utf-8"))
                tag = ConversationTag(**data)
                self._tags[tag.session_id] = tag
            except Exception:
                continue

    def tag(self, session_id: str, tag: str = "", favorite: bool = False, note: str = "") -> ConversationTag:
        item = self._tags.get(session_id) or ConversationTag(session_id=session_id)
        if tag:
            item.tag = tag
        if favorite:
            item.favorite = favorite
        if note:
            item.note = note
        item.created_at = time.time()
        self._tags[session_id] = item
        self._save(item)
        return item

    def get(self, session_id: str) -> Optional[ConversationTag]:
        return self._tags.get(session_id)

    def list_tags(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self._tags.values()]

    def _save(self, tag: ConversationTag) -> None:
        try:
            (_TAG_DIR / f"{tag.session_id}.json").write_text(
                json.dumps(tag.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


conversation_tagger = ConversationTagger()
