"""
PRISM Agent - 多设备同步
配置/技能跨设备同步
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

_SYNC_DIR = Path.home() / ".prism" / "multi_sync"
_SYNC_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SyncItem:
    key: str
    value: Any = None
    updated_at: float = field(default_factory=time.time)
    device: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at,
            "device": self.device,
        }


class MultiDeviceSync:
    def __init__(self) -> None:
        self._items: Dict[str, SyncItem] = {}
        self._load()

    def _load(self) -> None:
        for item_file in _SYNC_DIR.glob("*.json"):
            try:
                data = json.loads(item_file.read_text(encoding="utf-8"))
                item = SyncItem(**data)
                self._items[item.key] = item
            except Exception:
                continue

    def push(self, key: str, value: Any, device: str = "") -> SyncItem:
        item = self._items.get(key)
        if not item:
            item = SyncItem(key=key, value=value, device=device)
            self._items[key] = item
            self._save(item)
            return item
        item.value = value
        item.updated_at = time.time()
        if device:
            item.device = device
        self._save(item)
        return item

    def pull(self, key: str) -> Optional[SyncItem]:
        return self._items.get(key)

    def list_items(self) -> List[Dict[str, Any]]:
        return [i.to_dict() for i in self._items.values()]

    def _save(self, item: SyncItem) -> None:
        try:
            (_SYNC_DIR / f"{item.key}.json").write_text(
                json.dumps(item.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


multi_device_sync = MultiDeviceSync()
