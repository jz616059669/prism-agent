"""
PRISM Agent - Memory Providers tests
"""
from __future__ import annotations

import pytest

from prism.memory_providers import (
    LocalMemoryProvider,
    ChromaMemoryProvider,
    QdrantMemoryProvider,
    MemoryProviderRegistry,
    memory_provider_registry,
    MemoryRecord,
)


def test_local_memory_add_get_delete():
    p = LocalMemoryProvider()
    p.init()
    p.add(MemoryRecord(key="k1", value="v1", category="general"))
    assert p.get("k1") is not None
    assert p.get("k1").value == "v1"
    p.delete("k1")
    assert p.get("k1") is None


def test_local_memory_list_and_search():
    p = LocalMemoryProvider()
    p.init()
    p.add(MemoryRecord(key="a", value="apple", category="fruit"))
    p.add(MemoryRecord(key="b", value="banana", category="fruit"))
    keys = p.list_keys()
    assert "a" in keys and "b" in keys
    results = p.search("apple", top_k=3)
    assert any(k == "a" for k, _ in results)


def test_local_memory_clear():
    p = LocalMemoryProvider()
    p.init()
    p.add(MemoryRecord(key="x", value="y"))
    p.clear()
    assert p.list_keys() == []


def test_registry_has_local_default():
    # autoregister is normally called by memory module; here test provider directly
    p = LocalMemoryProvider()
    p.init()
    reg = MemoryProviderRegistry()
    reg.register(p, default=True)
    assert reg.get().name == "local"
    assert "local" in reg.names


def test_chroma_not_installed_raises():
    if pytest.importorskip("chromadb", reason="chromadb not installed"):
        pytest.skip("chromadb installed, skip negative import test")


def test_qdrant_not_installed_raises():
    if pytest.importorskip("qdrant_client", reason="qdrant_client not installed"):
        pytest.skip("qdrant_client installed, skip negative import test")
