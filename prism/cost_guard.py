"""
PRISM Agent - Cost Guard 成本守卫
实时成本监控+告警+熔断，防账单爆炸
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CostBudget:
    daily_usd: float = 5.0
    weekly_usd: float = 20.0
    monthly_usd: float = 80.0
    alert_threshold: float = 0.8


@dataclass
class CostRecord:
    ts: float = field(default_factory=time.time)
    amount_usd: float = 0.0
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "amount_usd": self.amount_usd,
            "model": self.model,
        }


class CostGuard:
    def __init__(self, budget: Optional[CostBudget] = None) -> None:
        self.budget = budget or CostBudget()
        self._records: List[CostRecord] = []
        self._circuit_open = False

    def record(self, amount_usd: float, model: str = "") -> CostRecord:
        record = CostRecord(ts=time.time(), amount_usd=amount_usd, model=model)
        self._records.append(record)
        if self._should_alert():
            logger.warning("cost guard alert: spent %.2f USD", self._total_spend())
        if self._should_trip():
            self._circuit_open = True
            logger.warning("cost guard tripped: spending limit reached")
        return record

    def can_spend(self, amount_usd: float) -> bool:
        if self._circuit_open:
            return False
        projected = self._total_spend() + amount_usd
        return projected <= self.budget.monthly_usd

    def status(self) -> Dict[str, Any]:
        total = self._total_spend()
        return {
            "total_usd": round(total, 4),
            "budget_daily_usd": self.budget.daily_usd,
            "budget_monthly_usd": self.budget.monthly_usd,
            "circuit_open": self._circuit_open,
            "can_spend": self.can_spend(0.0),
        }

    def _total_spend(self) -> float:
        now = time.time()
        month_start = now - 30 * 24 * 3600
        return sum(r.amount_usd for r in self._records if r.ts >= month_start)

    def _should_alert(self) -> bool:
        return self._total_spend() >= self.budget.monthly_usd * self.budget.alert_threshold

    def _should_trip(self) -> bool:
        return self._total_spend() >= self.budget.monthly_usd


cost_guard = CostGuard()
