"""
PRISM Agent - Memory 衰减
旧记忆自动降权，防止上下文被历史淹没
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DECAY_DIR = Path.home() / ".prism" / "memory_decay"
_DECAY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MemoryItem:
    id: str
    content: str = ""
    weight: float = 1.0
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "weight": round(self.weight, 4),
            "created_at": self.created_at,
            "accessed_at": self.accessed_at,
        }


class MemoryDecay:
    def __init__(self, half_life: float = 7 * 24 * 3600) -> None:
        self.half_life = half_life
        self._items: Dict[str, MemoryItem] = {}
        self._load()

    def _load(self) -> None:
        for item_file in _DECAY_DIR.glob("*.json"):
            try:
                data = json.loads(item_file.read_text(encoding="utf-8"))
                item = MemoryItem(**data)
                self._items[item.id] = item
            except Exception:
                continue

    def add(self, content: str, weight: float = 1.0) -> MemoryItem:
        item_id = f"mem_{int(time.time() * 1000)}"
        item = MemoryItem(id=item_id, content=content, weight=weight)
        self._items[item_id] = item
        self._save(item)
        return item

    def access(self, item_id: str) -> Optional[MemoryItem]:
        item = self._items.get(item_id)
        if not item:
            return None
        item.weight = 1.0
        item.accessed_at = time.time()
        self._save(item)
        return item

    def decay(self) -> List[MemoryItem]:
        now = time.time()
        updated = []
        for item in self._items.values():
            age = max(0.0, now - item.accessed_at)
            if age > 0:
                factor = 2 ** (-age / self.half_life)
                item.weight = max(0.0, item.weight * factor)
                self._save(item)
            updated.append(item)
        return updated

    def top(self, limit: int = 20) -> List[Dict[str, Any]]:
        items = sorted(self._items.values(), key=lambda x: x.weight, reverse=True)
        return [i.to_dict() for i in items[:limit]]

    def _save(self, item: MemoryItem) -> None:
        try:
            (_DECAY_DIR / f"{item.id}.json").write_text(
                json.dumps(item.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


memory_decay = MemoryDecay()
