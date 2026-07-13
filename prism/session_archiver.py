"""
PRISM Agent - 会话归档
旧会话自动压缩归档
"""

from __future__ import annotations

import gzip
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ARCHIVE_DIR = Path.home() / ".prism" / "archives"
_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ArchiveEntry:
    session_id: str
    size: int = 0
    compressed_size: int = 0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "size": self.size,
            "compressed_size": self.compressed_size,
            "created_at": self.created_at,
        }


class SessionArchiver:
    def archive(self, session_id: str, messages: List[Dict[str, Any]]) -> ArchiveEntry:
        raw = json.dumps({"session_id": session_id, "messages": messages}, ensure_ascii=False).encode("utf-8")
        entry = ArchiveEntry(session_id=session_id, size=len(raw))
        try:
            compressed = gzip.compress(raw)
            entry.compressed_size = len(compressed)
            (_ARCHIVE_DIR / f"{session_id}.json.gz").write_bytes(compressed)
        except Exception:
            try:
                (_ARCHIVE_DIR / f"{session_id}.json").write_bytes(raw)
            except Exception:
                pass
        return entry

    def list_archives(self) -> List[Dict[str, Any]]:
        archives = []
        for archive_file in _ARCHIVE_DIR.glob("*"):
            try:
                archives.append({
                    "name": archive_file.name,
                    "size": archive_file.stat().st_size,
                    "path": str(archive_file),
                })
            except Exception:
                continue
        archives.sort(key=lambda x: x.get("name", ""))
        return archives


session_archiver = SessionArchiver()
