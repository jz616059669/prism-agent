"""
PRISM Agent - Memory tests
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest
from prism.memory import PersistentMemory, Memory, MemoryEmbeddingIndex


@pytest.fixture()
def tmp_memory(tmp_path):
    return PersistentMemory(base_dir=tmp_path)


def test_remember_and_recall(tmp_memory):
    tmp_memory.remember("user.name", "贾总", category="profile")
    assert tmp_memory.recall("user.name") == "贾总"


def test_search_basic(tmp_memory):
    tmp_memory.remember("user.name", "贾总", category="profile")
    tmp_memory.remember("user.city", "宝鸡", category="profile")
    results = tmp_memory.search("贾总")
    values = [m.value for m in results]
    assert "贾总" in values


def test_get_context(tmp_memory):
    tmp_memory.remember("a", "1", category="c1")
    tmp_memory.remember("b", "2", category="c1")
    ctx = tmp_memory.get_context(max_items=1)
    assert "记忆上下文" in ctx


def test_summarize_empty(tmp_memory):
    assert tmp_memory.summarize() == ""


def test_decay_reduces_confidence(tmp_memory):
    tmp_memory.remember("temp", "v", category="test")
    tmp_memory.decay_half_life_days = 1
    mem = tmp_memory._index["temp"]
    from datetime import datetime, timedelta
    mem.last_accessed_at = (datetime.now() - timedelta(days=2)).isoformat()
    tmp_memory._apply_decay()
    assert mem.confidence < 1.0


def test_forget(tmp_memory):
    tmp_memory.remember("k", "v")
    assert tmp_memory.forget("k") is True
    assert tmp_memory.recall("k") is None


def test_auto_memory_path_str():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        m = PersistentMemory(base_dir=d)
        m.remember("x", "y")
        assert m.recall("x") == "y"
