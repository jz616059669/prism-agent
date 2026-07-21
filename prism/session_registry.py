"""
PRISM Agent - 统一会话注册表
管理 session 的 list / export / import / resume / search / compact。
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from prism.paths import PRISM_HOME
from prism.logging import logger

SESSION_DIR = PRISM_HOME / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)


class SessionRecord:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.stem = path.stem
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        self.messages = payload.get("messages", [])
        self.tags = payload.get("tags", [])
        self.created_at = payload.get("created_at", "")
        self.system_prompt = payload.get("system_prompt", "")
        self.message_count = len(self.messages)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.stem,
            "created_at": self.created_at,
            "tags": self.tags,
            "message_count": self.message_count,
            "preview": (self.messages[-1].get("content", "") if self.messages else "")[:120],
        }


class SessionRegistry:
    def list_sessions(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        try:
            for path in sorted(SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    rec = SessionRecord(path)
                    item = rec.to_dict()
                    if scope and scope not in item.get("tags", []) and scope != item.get("name"):
                        continue
                    records.append(item)
                except Exception:
                    continue
        except OSError:
            pass
        return records

    def get_session(self, name: str) -> Optional[Dict[str, Any]]:
        path = SESSION_DIR / f"{name}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def save_session(self, name: str, payload: Dict[str, Any]) -> Optional[Path]:
        try:
            path = SESSION_DIR / f"{name}.json"
            payload.setdefault("created_at", datetime.now().isoformat())
            payload.setdefault("tags", [])
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return path
        except OSError as exc:
            logger.debug("save session failed: %s", exc)
            return None

    def delete_session(self, name: str) -> bool:
        path = SESSION_DIR / f"{name}.json"
        try:
            if path.exists():
                path.unlink()
            return True
        except OSError:
            return False

    def export_sessions(self, names: List[str], dest: Optional[Path] = None) -> Optional[Path]:
        if dest is None:
            dest = PRISM_HOME / "exports" / f"sessions-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        bundle = {"exported_at": datetime.now().isoformat(), "sessions": {}}
        for name in names:
            payload = self.get_session(name)
            if payload:
                bundle["sessions"][name] = payload
        try:
            dest.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
            return dest
        except OSError as exc:
            logger.debug("export sessions failed: %s", exc)
            return None

    def import_sessions(self, source: Path) -> List[str]:
        imported: List[str] = []
        try:
            bundle = json.loads(source.read_text(encoding="utf-8"))
            sessions = bundle.get("sessions") or {}
            for name, payload in sessions.items():
                if self.save_session(name, payload):
                    imported.append(name)
        except Exception as exc:
            logger.debug("import sessions failed: %s", exc)
        return imported

    def search_sessions(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        q = (query or "").lower().strip()
        if not q:
            return self.list_sessions()[: max(0, limit)]
        try:
            for path in sorted(SESSION_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                hit = False
                content_hit = ""
                for msg in payload.get("messages", []):
                    if q in msg.get("content", "").lower():
                        hit = True
                        content_hit = msg.get("content", "")[:180]
                        break
                if not hit:
                    tags = payload.get("tags") or []
                    if any(q in tag.lower() for tag in tags):
                        hit = True
                        content_hit = "tags: " + ", ".join(tags)
                if hit:
                    results.append({
                        "name": path.stem,
                        "preview": content_hit,
                        "created_at": payload.get("created_at", ""),
                        "message_count": len(payload.get("messages", [])),
                    })
                if len(results) >= max(0, limit):
                    break
        except OSError:
            pass
        return results

    def compact_session(self, name: str) -> Dict[str, Any]:
        payload = self.get_session(name)
        if not payload:
            return {"success": False, "error": "session not found"}
        try:
            from prism.context_compactor import context_compactor
            messages = payload.get("messages", [])
            summary = context_compactor.compact(name, messages)
            compacted = {
                "system_prompt": payload.get("system_prompt", ""),
                "messages": [
                    {"role": "system", "content": summary.summary or ""},
                    {"role": "user", "content": "[上下文已压缩]" },
                ],
                "tags": payload.get("tags", []),
                "created_at": payload.get("created_at", datetime.now().isoformat()),
            }
            self.save_session(name, compacted)
            return {"success": True, "summary": summary.summary}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


session_registry = SessionRegistry()
