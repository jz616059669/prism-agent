"""
PRISM Agent - Memory 版本控制
记忆快照/回滚/diff，像 Git 一样管理记忆
"""

from __future__ import annotations

import difflib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MEMORY_DIR = Path.home() / ".prism" / "memory"
_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
_SNAP_DIR = _MEMORY_DIR / "_snapshots"
_SNAP_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MemorySnapshot:
    category: str
    content: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "content": self.content,
            "created_at": self.created_at,
        }


class MemoryVersionControl:
    def snapshot(self, category: str, content: str) -> MemorySnapshot:
        snap = MemorySnapshot(category=category, content=content)
        try:
            (_SNAP_DIR / f"{category}_{int(snap.created_at)}.json").write_text(
                json.dumps(snap.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
        return snap

    def list_snapshots(self, category: str) -> List[Dict[str, Any]]:
        snaps: List[Dict[str, Any]] = []
        for snap_file in _SNAP_DIR.glob(f"{category}_*.json"):
            try:
                data = json.loads(snap_file.read_text(encoding="utf-8"))
                snaps.append(data)
            except Exception:
                continue
        snaps.sort(key=lambda x: x.get("created_at", 0))
        return snaps

    def rollback(self, category: str, target_ts: float) -> bool:
        snaps = self.list_snapshots(category)
        target = next((s for s in snaps if s.get("created_at") == target_ts), None)
        if not target:
            return False
        target_file = _MEMORY_DIR / f"{category}.jsonl"
        try:
            target_file.write_text((target.get("content") or ""), encoding="utf-8")
            return True
        except Exception:
            return False

    def diff(self, category: str, from_ts: float, to_ts: float) -> str:
        snaps = self.list_snapshots(category)
        from_snap = next((s for s in snaps if s.get("created_at") == from_ts), None)
        to_snap = next((s for s in snaps if s.get("created_at") == to_ts), None)
        if not from_snap or not to_snap:
            return ""
        from_lines = (from_snap.get("content") or "").splitlines()
        to_lines = (to_snap.get("content") or "").splitlines()
        diff = difflib.unified_diff(from_lines, to_lines, lineterm="")
        return "\n".join(list(diff)[:200])


memory_vcs = MemoryVersionControl()
