"""
PRISM Agent - Freshness / search tests
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

from prism.tools.freshness import freshness_tag, apply_freshness_to_search_result, filter_stale_results, now_utc
from datetime import datetime, timezone, timedelta


def test_freshness_tag_fresh():
    ts = (now_utc() - timedelta(minutes=5)).isoformat()
    tag = freshness_tag(ts, max_age_minutes=60)
    assert tag["status"] == "fresh"
    assert tag["age_minutes"] <= 60


def test_freshness_tag_stale():
    ts = (now_utc() - timedelta(minutes=120)).isoformat()
    tag = freshness_tag(ts, max_age_minutes=60)
    assert tag["status"] == "stale"
    assert tag["age_minutes"] >= 100


def test_freshness_tag_invalid():
    tag = freshness_tag("not-a-time", max_age_minutes=60)
    assert tag["status"] == "invalid"
    assert tag["reason"] == "unparseable_timestamp"


def test_freshness_tag_missing():
    tag = freshness_tag(None, max_age_minutes=60)
    assert tag["status"] == "unknown"
    assert tag["reason"] == "missing_timestamp"


def test_apply_freshness_to_search_result():
    item = {
        "title": "x",
        "url": "http://example.com",
        "snippet": "y",
        "fetched_at": (now_utc() - timedelta(minutes=2)).isoformat(),
    }
    out = apply_freshness_to_search_result(item, max_age_minutes=60)
    assert out["freshness"]["status"] == "fresh"
    assert out["title"] == "x"


def test_filter_stale_results():
    results = [
        {"title": "fresh", "fetched_at": (now_utc() - timedelta(minutes=2)).isoformat(), "url": "a"},
        {"title": "stale", "fetched_at": (now_utc() - timedelta(minutes=200)).isoformat(), "url": "b"},
    ]
    kept = filter_stale_results(results, max_age_minutes=60)
    assert len(kept) == 1
    assert kept[0]["title"] == "fresh"
