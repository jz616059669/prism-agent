"""
PRISM Agent - 集成测试：Provider 重试/退避 + 记忆系统边界
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_memory_remember_recall_and_search(tmp_path):
    from prism.memory import PersistentMemory
    mem = PersistentMemory(base_dir=tmp_path)
    mem.remember("user.name", "贾总", category="profile")
    mem.remember("user.city", "宝鸡", category="profile")
    assert mem.recall("user.name") == "贾总"
    results = mem.search("贾总")
    values = [m.value for m in results]
    assert "贾总" in values


def test_memory_decay_and_forget(tmp_path):
    from prism.memory import PersistentMemory
    from datetime import datetime, timedelta

    mem = PersistentMemory(base_dir=tmp_path)
    mem.remember("temp", "v", category="test")
    mem.decay_half_life_days = 1
    entry = mem._index["temp"]
    entry.created_at = (datetime.now() - timedelta(days=2)).isoformat()
    mem._apply_decay()
    assert entry.confidence < 1.0
    assert mem.forget("temp") is True
    assert mem.recall("temp") is None
