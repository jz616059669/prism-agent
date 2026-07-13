"""
PRISM Agent - task_feedback tests
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from prism.task_feedback import record_failure, apply_strategies, update_strategy, review_and_update, _load_strategies, _save_strategies


def test_record_failure_creates_strategy(tmp_path):
    with patch("prism.task_feedback._FEEDBACK_DIR", tmp_path), patch("prism.task_feedback._FEEDBACK_FILE", tmp_path / "strategies.json"):
        res = record_failure("read file", "FileNotFoundError")
        assert res["success"] is True
        assert "key" in res
        items = _load_strategies()
        assert any(s.get("task") == "read file" for s in items)


def test_apply_strategies_empty_when_none():
    with patch("prism.task_feedback._load_strategies", return_value=[]):
        assert apply_strategies("read file") == []


def test_update_strategy_not_found():
    with patch("prism.task_feedback._load_strategies", return_value=[]), \
         patch("prism.task_feedback._save_strategies"):
        res = update_strategy("missing", "retry")
    assert res["success"] is False
