"""
PRISM Agent - Token 计数/预算
精确计算每次请求 token 用量，预估成本
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BUDGET_DIR = Path.home() / ".prism" / "budget"
_BUDGET_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class TokenUsage:
    ts: float = field(default_factory=time.time)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "model": self.model,
        }


class TokenCounter:
    _PRICE_PER_1K = {
        "gpt-4o": {"prompt": 0.005, "completion": 0.015},
        "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
        "claude-3-5-sonnet": {"prompt": 0.003, "completion": 0.015},
        "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125},
        "step-3.7-flash": {"prompt": 0.002, "completion": 0.006},
    }

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        price = self._PRICE_PER_1K.get(model, {}).get("prompt", 0.0)
        price_out = self._PRICE_PER_1K.get(model, {}).get("completion", 0.0)
        return (prompt_tokens / 1000.0) * price + (completion_tokens / 1000.0) * price_out

    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> TokenUsage:
        total = prompt_tokens + completion_tokens
        cost = self.estimate_cost(model, prompt_tokens, completion_tokens)
        usage = TokenUsage(ts=time.time(), prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=total, cost_usd=cost, model=model)
        try:
            with (_BUDGET_DIR / "usage.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(usage.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass
        return usage

    def monthly_spend(self, days: int = 30) -> float:
        now = time.time()
        total = 0.0
        try:
            path = _BUDGET_DIR / "usage.jsonl"
            if not path.exists():
                return 0.0
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("ts", 0) >= now - days * 24 * 3600:
                        total += data.get("cost_usd", 0.0)
                except Exception:
                    continue
        except Exception:
            pass
        return total


token_counter = TokenCounter()
