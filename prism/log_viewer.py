"""
PRISM Agent - 日志查看器
本地日志 + 过滤 + 导出
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_LOG_DIR = Path.home() / ".prism" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class LogEntry:
    ts: str = ""
    level: str = "INFO"
    logger: str = ""
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
        }


class LogViewer:
    def tail(self, log_file: str = "prism.jsonl", lines: int = 100) -> List[Dict[str, Any]]:
        path = _LOG_DIR / log_file
        if not path.exists():
            return []
        try:
            entries = [line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
            result = []
            for line in entries[-lines:]:
                try:
                    result.append(json.loads(line))
                except Exception:
                    continue
            return result
        except Exception:
            return []

    def filter(self, level: str = "", keyword: str = "", log_file: str = "prism.jsonl", lines: int = 500) -> List[Dict[str, Any]]:
        entries = self.tail(log_file=log_file, lines=lines)
        filtered = []
        for entry in entries:
            if level and entry.get("level", "").lower() != level.lower():
                continue
            if keyword and keyword.lower() not in (entry.get("message", "") or "").lower():
                continue
            filtered.append(entry)
        return filtered

    def export(self, output_path: str, entries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        entries = entries or self.tail()
        try:
            Path(output_path).write_text(
                json.dumps(entries, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return {"success": True, "path": output_path, "count": len(entries)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


log_viewer = LogViewer()
