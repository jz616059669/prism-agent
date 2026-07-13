"""
PRISM Agent - usage tests
"""
from __future__ import annotations

import time

from prism.usage import UsageTracker, usage_tracker


def test_usage_record_and_stats():
    tracker = UsageTracker()
    tracker.record(model="gpt-4o", prompt_tokens=100, completion_tokens=50, latency_ms=120.0, success=True)
    tracker.record(model="gpt-4o", prompt_tokens=200, completion_tokens=80, latency_ms=250.0, success=False, error_type="rate_limit")
    s = tracker.stats()
    assert s["total_calls"] == 2
    assert s["success_rate"] == 50.0
    assert s["total_prompt_tokens"] == 300
    assert s["total_completion_tokens"] == 130
    assert "by_model" in s


def test_usage_cost():
    tracker = UsageTracker()
    tracker.record(model="step-3.7-flash", prompt_tokens=1_000_000, completion_tokens=1_000_000, latency_ms=100.0)
    s = tracker.stats()
    # 2.5 + 10 = 12.5 for gpt-4o; step-3.7-flash: 0.5 + 2 = 2.5
    assert round(s["total_cost_usd"], 2) == 2.5
