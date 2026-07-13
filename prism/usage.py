"""
PRISM Agent - 对话数据仪表盘
统计 token 消耗、模型调用成本、任务成功率、延迟
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_USAGE_DIR = Path.home() / ".prism" / "usage"
_USAGE_DIR.mkdir(parents=True, exist_ok=True)
_USAGE_FILE = _USAGE_DIR / "usage.jsonl"

# 粗略成本表（$/1M tokens），可按需扩展
_MODEL_COSTS: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"prompt": 2.5, "completion": 10.0},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.6},
    "claude-3-5-sonnet": {"prompt": 3.0, "completion": 15.0},
    "step-3.7-flash": {"prompt": 0.5, "completion": 2.0},
    "step-2-16k": {"prompt": 1.0, "completion": 2.0},
}


@dataclass
class UsageRecord:
    ts: float
    session_id: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error_type: str = ""


class UsageTracker:
    def __init__(self) -> None:
        self._records: List[UsageRecord] = []

    def record(self, model: str, prompt_tokens: int = 0, completion_tokens: int = 0,
               latency_ms: float = 0.0, success: bool = True, error_type: str = "", session_id: str = "") -> None:
        rec = UsageRecord(
            ts=time.time(),
            session_id=session_id or "default",
            model=model,
            prompt_tokens=max(0, prompt_tokens),
            completion_tokens=max(0, completion_tokens),
            latency_ms=max(0.0, latency_ms),
            success=success,
            error_type=error_type or "",
        )
        self._records.append(rec)
        try:
            with _USAGE_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
        except Exception:
            pass

    def stats(self) -> Dict[str, Any]:
        total = len(self._records)
        if total == 0:
            return {"total_calls": 0, "success_rate": 0.0, "total_prompt_tokens": 0,
                    "total_completion_tokens": 0, "total_cost_usd": 0.0, "avg_latency_ms": 0.0}
        success = sum(1 for r in self._records if r.success)
        prompt = sum(r.prompt_tokens for r in self._records)
        comp = sum(r.completion_tokens for r in self._records)
        cost = sum(self._cost(r) for r in self._records)
        latency = sum(r.latency_ms for r in self._records) / total
        return {
            "total_calls": total,
            "success_rate": round(success / total * 100, 1),
            "total_prompt_tokens": prompt,
            "total_completion_tokens": comp,
            "total_cost_usd": round(cost, 4),
            "avg_latency_ms": round(latency, 1),
            "by_model": self._by_model(),
        }

    def recent(self, n: int = 20) -> List[Dict[str, Any]]:
        rows = list(self._records[-n:])
        return [asdict(r) for r in rows]

    def _by_model(self) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for r in self._records:
            m = out.setdefault(r.model, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "errors": 0})
            m["calls"] += 1
            m["prompt_tokens"] += r.prompt_tokens
            m["completion_tokens"] += r.completion_tokens
            if not r.success:
                m["errors"] += 1
        return out

    def _cost(self, r: UsageRecord) -> float:
        table = _MODEL_COSTS.get(r.model, {})
        prompt_rate = table.get("prompt", 0.0)
        comp_rate = table.get("completion", 0.0)
        return (r.prompt_tokens * prompt_rate + r.completion_tokens * comp_rate) / 1_000_000

    def load(self) -> None:
        if not _USAGE_FILE.exists():
            return
        try:
            with _USAGE_FILE.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        self._records.append(UsageRecord(**data))
                    except Exception:
                        continue
        except Exception:
            pass


# 全局单例
usage_tracker = UsageTracker()
usage_tracker.load()
