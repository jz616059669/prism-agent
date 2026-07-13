"""
PRISM Agent - 审计日志
结构化操作审计，不可篡改，满足合规
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_AUDIT_DIR = Path.home() / ".prism" / "audit"
_AUDIT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AuditEntry:
    ts: float = field(default_factory=time.time)
    actor: str = ""
    action: str = ""
    target: str = ""
    result: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "actor": self.actor,
            "action": self.action,
            "target": self.target,
            "result": self.result,
            "metadata": self.metadata,
            "prev_hash": self.prev_hash,
        }


class AuditLog:
    def __init__(self) -> None:
        self._entries: List[AuditEntry] = []
        self._last_hash = ""
        self._load()

    def _load(self) -> None:
        audit_file = _AUDIT_DIR / "audit.jsonl"
        if not audit_file.exists():
            return
        try:
            lines = [line for line in audit_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            if lines:
                last = json.loads(lines[-1])
                self._last_hash = last.get("hash", "")
        except Exception:
            pass

    def append(self, entry: AuditEntry) -> AuditEntry:
        entry.prev_hash = self._last_hash
        payload = json.dumps(entry.to_dict(), ensure_ascii=False, sort_keys=True).encode("utf-8")
        entry_hash = hashlib.sha256(payload).hexdigest()[:16]
        try:
            with (_AUDIT_DIR / "audit.jsonl").open("a", encoding="utf-8") as f:
                data = dict(entry.to_dict())
                data["hash"] = entry_hash
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception:
            pass
        self._last_hash = entry_hash
        self._entries.append(entry)
        return entry

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._entries[-limit:]]


audit_log = AuditLog()
