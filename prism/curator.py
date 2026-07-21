"""
PRISM Agent - Curator
技能/记忆/会话生命周期管理：整理、归档、清理、去重。
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from prism.logging import logger

PRISM_HOME = Path.home() / ".prism"
SESSIONS_DIR = PRISM_HOME / "sessions"
SKILLS_DIR = PRISM_HOME / "skills"
TRACES_DIR = PRISM_HOME / "traces"
AUDIT_DIR = PRISM_HOME / "audit"


class Curator:
    def __init__(self, retention_days: int = 30, max_sessions: int = 100, max_traces: int = 200) -> None:
        self.retention_days = retention_days
        self.max_sessions = max_sessions
        self.max_traces = max_traces

    def run(self) -> Dict[str, Any]:
        result = {
            "sessions": self._curate_sessions(),
            "traces": self._curate_traces(),
            "audit": self._curate_audit(),
            "skills": self._curate_skills(),
        }
        return result

    def _curate_sessions(self) -> Dict[str, Any]:
        try:
            files = sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            return {"removed": 0, "kept": 0}
        kept = files[: self.max_sessions]
        removed = files[self.max_sessions :]
        for old in removed:
            try:
                old.unlink()
            except OSError:
                pass
        return {"removed": len(removed), "kept": len(kept)}

    def _curate_traces(self) -> Dict[str, Any]:
        try:
            files = sorted(TRACES_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            return {"removed": 0, "kept": 0}
        kept = files[: self.max_traces]
        removed = files[self.max_traces :]
        for old in removed:
            try:
                old.unlink()
            except OSError:
                pass
        return {"removed": len(removed), "kept": len(kept)}

    def _curate_audit(self) -> Dict[str, Any]:
        try:
            cutoff = time.time() - self.retention_days * 86400
            removed = 0
            kept = 0
            for path in AUDIT_DIR.glob("*.jsonl"):
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        removed += 1
                    else:
                        kept += 1
                except OSError:
                    pass
            return {"removed": removed, "kept": kept}
        except OSError:
            return {"removed": 0, "kept": 0}

    def _curate_skills(self) -> Dict[str, Any]:
        try:
            if not SKILLS_DIR.exists():
                return {"removed": 0, "kept": 0}
            removed = 0
            kept = 0
            for path in SKILLS_DIR.rglob("SKILL.md"):
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    if "created_by: \"agent\"" not in text:
                        kept += 1
                        continue
                    mtime = path.stat().st_mtime
                    if time.time() - mtime > self.retention_days * 86400:
                        # archive instead of delete
                        archive_dir = PRISM_HOME / "archived_skills"
                        archive_dir.mkdir(parents=True, exist_ok=True)
                        target = archive_dir / f"{path.parent.name}_{int(mtime)}"
                        try:
                            path.parent.rename(target)
                            removed += 1
                        except OSError:
                            kept += 1
                    else:
                        kept += 1
                except OSError:
                    pass
            return {"removed": removed, "kept": kept}
        except OSError:
            return {"removed": 0, "kept": 0}


curator = Curator()
