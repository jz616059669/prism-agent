"""
PRISM Agent - 外部数据新鲜度校验
用于搜索结果、新闻、价格等带时间戳数据的 freshness 校验。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("prism.freshness")


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        value = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(value)
    except Exception:
        return None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def freshness_tag(ts: Optional[str], max_age_minutes: int = 60) -> Dict[str, Any]:
    """
    返回 freshness 标签：
      - fresh / stale / unknown / invalid
    并附带 age_minutes / max_age_minutes / issued_at / checked_at
    """
    checked_at = now_utc()
    if not ts:
        return {
            "status": "unknown",
            "reason": "missing_timestamp",
            "age_minutes": None,
            "max_age_minutes": max_age_minutes,
            "issued_at": None,
            "checked_at": checked_at.isoformat(),
        }

    parsed = _parse_iso(ts)
    if parsed is None:
        return {
            "status": "invalid",
            "reason": "unparseable_timestamp",
            "age_minutes": None,
            "max_age_minutes": max_age_minutes,
            "issued_at": ts,
            "checked_at": checked_at.isoformat(),
        }

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    age = (checked_at - parsed).total_seconds() / 60.0
    status = "fresh" if age <= max_age_minutes else "stale"

    return {
        "status": status,
        "reason": "ok" if status == "fresh" else "too_old",
        "age_minutes": round(age, 2),
        "max_age_minutes": max_age_minutes,
        "issued_at": parsed.isoformat(),
        "checked_at": checked_at.isoformat(),
    }


def apply_freshness_to_search_result(item: Dict[str, Any], max_age_minutes: int = 60) -> Dict[str, Any]:
    """给单个搜索结果附加 freshness 字段"""
    out = dict(item)
    out["freshness"] = freshness_tag(item.get("fetched_at"), max_age_minutes=max_age_minutes)
    return out


def filter_stale_results(results: List[Dict[str, Any]], max_age_minutes: int = 60) -> List[Dict[str, Any]]:
    """过滤掉 stale 搜索结果；unknown/invalid 也排除，避免误用"""
    kept: List[Dict[str, Any]] = []
    for item in results:
        tagged = apply_freshness_to_search_result(item, max_age_minutes=max_age_minutes)
        if tagged["freshness"].get("status") == "fresh":
            kept.append(tagged)
        else:
            logger.debug(
                "drop stale search result: status=%s age=%s url=%s",
                tagged["freshness"].get("status"),
                tagged["freshness"].get("age_minutes"),
                item.get("url"),
            )
    return kept
