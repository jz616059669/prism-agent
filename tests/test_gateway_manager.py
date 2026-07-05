"""
PRISM Agent - Gateway manager tests
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest

class FakeResp:
    def __init__(self, data, status=200):
        self._data = data
        self.status_code = status
        self.text = str(data)

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_gateway_send_dispatches_to_adapter(monkeypatch):
    from prism.gateway import Gateway
    from prism.gateway.telegram import TelegramAdapter, TelegramConfig

    import prism.gateway.telegram as telegram_mod
    telegram_mod.requests.post = lambda url, **kwargs: FakeResp({"ok": True})

    gw = Gateway()
    adapter = TelegramAdapter(TelegramConfig(bot_token="t"))
    gw.register("telegram", adapter)

    assert gw.send("telegram", "1", "hi") is True
    assert gw.send("unknown", "1", "hi") is False


def test_gateway_list_platforms_from_config(monkeypatch, tmp_path):
    from prism.gateway import Gateway
    import prism.paths as paths_mod
    import prism.config as config_mod

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        "gateway:\n  platforms:\n    - feishu\n    - telegram\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(paths_mod, "PRISM_HOME", tmp_path, raising=False)

    # Force config to use new PRISM_HOME and reload
    cfg = config_mod.config
    cfg.config_dir = tmp_path
    cfg.config_file = tmp_path / "config.yaml"
    cfg._config = None
    cfg._load()

    gw = Gateway()
    platforms = gw.list_platforms()
    assert "feishu" in platforms
    assert "telegram" in platforms


def test_gateway_start_stop_lifecycle(monkeypatch):
    from prism.gateway import Gateway
    from prism.gateway.telegram import TelegramAdapter, TelegramConfig

    import prism.gateway.telegram as telegram_mod
    telegram_mod.requests.get = lambda url, **kwargs: FakeResp({"ok": True, "result": []})

    class LifeAdapter:
        def __init__(self, name):
            self.name = name
            self.handler = None
            self.running = False

        def start_polling(self, handler):
            self.handler = handler
            self.running = True

        def stop(self):
            self.running = False
            self.handler = None

        def send(self, chat_id, text):
            return True

    gw = Gateway()
    adapter = LifeAdapter("x")
    gw.register("x", adapter)

    handler_calls = []

    def handler(msg):
        handler_calls.append(msg)

    gw.start(handler)
    assert gw.running is True
    assert adapter.running is True
    assert adapter.handler is handler

    gw.stop()
    assert gw.running is False
    assert adapter.running is False
    assert adapter.handler is None
