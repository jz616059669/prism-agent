"""
PRISM Agent - Self-improvement loop
任务失败后自动分析并生成可复用改进策略，注入后续执行
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_FEEDBACK_DIR = Path.home() / ".prism" / "feedback"
_FEEDBACK_FILE = _FEEDBACK_DIR / "strategies.json"


def _ensure_feedback_dir() -> None:
    try:
        _FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _load_strategies() -> List[Dict[str, Any]]:
    _ensure_feedback_dir()
    if not _FEEDBACK_FILE.exists():
        return []
    try:
        data = json.loads(_FEEDBACK_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception as exc:
        logger.debug("load strategies failed: %s", exc)
    return []


def _save_strategies(strategies: List[Dict[str, Any]]) -> None:
    try:
        _ensure_feedback_dir()
        _FEEDBACK_FILE.write_text(json.dumps(strategies, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        logger.debug("save strategies failed: %s", exc)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def record_failure(task: str, error: str, context: Optional[str] = None) -> Dict[str, Any]:
    strategies = _load_strategies()
    key = _hash(task)
    existing = next((s for s in strategies if s.get("key") == key), None)
    if existing:
        existing["count"] = int(existing.get("count", 0)) + 1
        existing["last_error"] = error
        existing["updated_at"] = _now()
    else:
        strategies.append({
            "key": key,
            "task": task,
            "error": error,
            "context": context or "",
            "count": 1,
            "created_at": _now(),
            "updated_at": _now(),
            "strategy": "",
        })
    _save_strategies(strategies)
    return {"success": True, "key": key}


def apply_strategies(task: str, limit: int = 3) -> List[str]:
    strategies = _load_strategies()
    key = _hash(task)
    hits = [s for s in strategies if s.get("key") == key and s.get("strategy")]
    if not hits:
        return []
    hits.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return [s.get("strategy", "") for s in hits[: max(1, limit)]]


def update_strategy(key: str, strategy: str) -> Dict[str, Any]:
    strategies = _load_strategies()
    item = next((s for s in strategies if s.get("key") == key), None)
    if not item:
        return {"success": False, "error": "strategy not found"}
    item["strategy"] = strategy
    item["updated_at"] = _now()
    _save_strategies(strategies)
    return {"success": True}


def analyze_and_generate_strategy(task: str, error: str, context: str = "") -> str:
    prompt = (
        "分析以下失败任务并生成可复用改进策略，输出应简洁可执行。\n"
        f"任务：{task}\n"
        f"错误：{error}\n"
        f"上下文：{context}\n"
        "策略："
    )
    try:
        from prism.agent import create_agent
        agent = create_agent(enable_auto_memory=False)
        text = agent.chat(user_message=prompt)
        if text:
            return text.strip()
    except (ImportError, Exception) as exc:
        logger.debug("strategy generation failed: %s", exc)
    return ""


def review_and_update() -> Dict[str, Any]:
    strategies = _load_strategies()
    updated = 0
    for item in strategies:
        if item.get("strategy"):
            continue
        task = item.get("task", "")
        error = item.get("error", "")
        context = item.get("context", "")
        if not task or not error:
            continue
        strategy = analyze_and_generate_strategy(task, error, context)
        if strategy:
            update_strategy(item.get("key", ""), strategy)
            updated += 1
    return {"success": True, "updated": updated}


def _now() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")
