"""
PRISM Agent - Providers tests
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.providers.manager import ProviderPool, OpenAIProvider


def test_provider_pool_retry_on_transient(monkeypatch):
    pool = ProviderPool()
    calls = {"count": 0}

    class FakeProvider:
        name = "fake"
        def chat(self, messages, **kwargs):
            calls["count"] += 1
            if calls["count"] < 3:
                return {"success": False, "error": "503 Service Unavailable"}
            return {"success": True, "content": "ok"}

    monkeypatch.setattr(pool, "_load_from_config", lambda: None)
    pool.providers = [FakeProvider()]
    result = pool.chat([{"role": "user", "content": "hi"}])
    assert result["success"] is True
    assert calls["count"] == 3


def test_provider_pool_no_retry_on_auth(monkeypatch):
    pool = ProviderPool()

    class FakeProvider:
        name = "fake"
        def chat(self, messages, **kwargs):
            return {"success": False, "error": "401 Invalid API Key"}

    monkeypatch.setattr(pool, "_load_from_config", lambda: None)
    pool.providers = [FakeProvider()]
    result = pool.chat([{"role": "user", "content": "hi"}])
    assert result["success"] is False
    assert "401" in result.get("error", "")


def test_provider_pool_empty():
    pool = ProviderPool()
    pool.providers = []
    result = pool.chat([{"role": "user", "content": "hi"}])
    assert result["success"] is False


def test_set_default_model_updates_providers_and_config(monkeypatch):
    pool = ProviderPool()

    class FakeProvider:
        name = "fake"
        model = "old-model"
        def chat(self, messages, **kwargs):
            return {"success": True, "content": "ok"}

    pool.providers = [FakeProvider()]
    monkeypatch.setattr(pool, "_load_from_config", lambda: None)

    saved = {}

    def fake_set(key, value):
        saved[key] = value

    monkeypatch.setattr("prism.config.get_config", lambda: type("Cfg", (), {"set": staticmethod(fake_set)})())

    result = pool.set_default_model("new-model")
    assert result["success"] is True
    assert result["model"] == "new-model"
    assert result["updated_providers"] == 1
    assert saved.get("model.default") == "new-model"
    assert pool.providers[0].model == "new-model"
