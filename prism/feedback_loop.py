"""
PRISM Agent - 自我改进闭环
从失败中学习：记录失败模式，后续类似任务自动注入规避提示。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("prism.feedback")

_FEEDBACK_DIR = Path.home() / ".prism" / "feedback"
_FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
_FAILURE_FILE = _FEEDBACK_DIR / "failures.jsonl"
_HINT_LIMIT = 120


def record_failure(task: str, error: str, context: str = "", user: str = "") -> None:
    try:
        key = _make_key(task, context)
        record = {
            "ts": datetime.now().isoformat(),
            "task": task,
            "context": (context or "")[:_HINT_LIMIT],
            "error": (error or "")[:_HINT_LIMIT],
            "user": user,
            "key": key,
        }
        with _FAILURE_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        logger.debug("record failure failed", exc_info=True)


def load_hints(task: str, context: str = "") -> List[str]:
    hints: List[str] = []
    try:
        if not _FAILURE_FILE.exists():
            return hints
        key = _make_key(task, context)
        seen = set()
        with _FAILURE_FILE.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    item = json.loads(line)
                except Exception:
                    continue
                if item.get("key") != key:
                    continue
                error = (item.get("error") or "").strip()
                if not error or error in seen:
                    continue
                seen.add(error)
                hints.append(f"之前失败过：{error}")
                if len(hints) >= 3:
                    break
    except Exception:
        logger.debug("load hints failed", exc_info=True)
    return hints


def build_context_injection(task: str, context: str = "") -> str:
    hints = load_hints(task, context)
    if not hints:
        return ""
    lines = ["【历史失败提示】"] + [f"- {h}" for h in hints] + ["请避免重蹈覆辙。"]
    return "\n".join(lines)


def _make_key(task: str, context: str) -> str:
    raw = f"{task}:{(context or '')[:80]}"
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]
