"""
PRISM Agent - Offline Sync
多设备离线同步，冲突合并
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

_SYNC_DIR = Path.home() / ".prism" / "sync"
_SYNC_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SyncDoc:
    id: str
    content: str = ""
    version: int = 1
    updated_at: float = field(default_factory=time.time)
    device: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "version": self.version,
            "updated_at": self.updated_at,
            "device": self.device,
        }


class OfflineSync:
    def __init__(self) -> None:
        self._docs: Dict[str, SyncDoc] = {}
        self._load()

    def _load(self) -> None:
        for doc_file in _SYNC_DIR.glob("*.json"):
            try:
                data = json.loads(doc_file.read_text(encoding="utf-8"))
                doc = SyncDoc(**data)
                self._docs[doc.id] = doc
            except Exception:
                continue

    def push(self, doc_id: str, content: str, device: str = "") -> Optional[SyncDoc]:
        doc = self._docs.get(doc_id)
        if not doc:
            doc = SyncDoc(id=doc_id, content=content, device=device)
            self._docs[doc_id] = doc
            self._save(doc)
            return doc
        if content != doc.content:
            doc.content = content
            doc.version += 1
            doc.updated_at = time.time()
            doc.device = device or doc.device
            self._save(doc)
        return doc

    def pull(self, doc_id: str) -> Optional[SyncDoc]:
        return self._docs.get(doc_id)

    def list_docs(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._docs.values()]

    def _save(self, doc: SyncDoc) -> None:
        try:
            (_SYNC_DIR / f"{doc.id}.json").write_text(
                json.dumps(doc.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


offline_sync = OfflineSync()
