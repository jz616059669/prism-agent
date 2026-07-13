"""
PRISM Agent - 协作编辑
多人同时编辑同一文档/对话，本地 JSON 文档 + 版本号 + 操作日志
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

_COLLAB_EDIT_DIR = Path.home() / ".prism" / "collab_edit"
_COLLAB_EDIT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class EditOp:
    id: str = ""
    type: str = "replace"  # replace | insert | delete
    path: str = ""
    content: str = ""
    author: str = ""
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "path": self.path,
            "content": self.content,
            "author": self.author,
            "ts": self.ts,
        }


@dataclass
class CollabDoc:
    id: str
    title: str = ""
    content: str = ""
    version: int = 1
    ops: List[EditOp] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "version": self.version,
            "ops": [o.to_dict() for o in self.ops],
        }


class CollabEditor:
    def __init__(self) -> None:
        self._docs: Dict[str, CollabDoc] = {}
        self._load()

    def _load(self) -> None:
        for doc_file in _COLLAB_EDIT_DIR.glob("*.json"):
            try:
                data = json.loads(doc_file.read_text(encoding="utf-8"))
                doc = CollabDoc(**data)
                doc.ops = [EditOp(**o) for o in data.get("ops", [])]
                self._docs[doc.id] = doc
            except Exception:
                continue

    def create(self, doc_id: str, title: str = "", content: str = "") -> CollabDoc:
        doc = CollabDoc(id=doc_id, title=title, content=content)
        self._docs[doc.id] = doc
        self._save(doc)
        return doc

    def apply(self, doc_id: str, op: EditOp) -> Optional[CollabDoc]:
        doc = self._docs.get(doc_id)
        if not doc:
            return None
        if op.type == "replace":
            doc.content = op.content
        elif op.type == "insert":
            doc.content = doc.content + "\n" + op.content
        elif op.type == "delete":
            doc.content = doc.content.replace(op.content, "")
        doc.version += 1
        op.id = f"op_{doc.version}_{int(time.time())}"
        doc.ops.append(op)
        self._save(doc)
        return doc

    def get(self, doc_id: str) -> Optional[CollabDoc]:
        return self._docs.get(doc_id)

    def list_docs(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._docs.values()]

    def _save(self, doc: CollabDoc) -> None:
        try:
            (_COLLAB_EDIT_DIR / f"{doc.id}.json").write_text(
                json.dumps(doc.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


collab_editor = CollabEditor()
