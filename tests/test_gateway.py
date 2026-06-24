"""Gateway 平台适配器真实连接测试（monkeypatch HTTP）"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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


class FakeSession:
    def __init__(self, data):
        self._data = data

    def post(self, url, **kwargs):
        return FakeResp(self._data.get("post", {"ok": True}))

    def get(self, url, **kwargs):
        return FakeResp(self._data.get("get", {"ok": True}))

    def close(self):
        pass


def test_telegram_adapter_send():
    from prism.gateway.telegram import TelegramAdapter, TelegramConfig
    import prism.gateway.telegram as telegram_mod

    responses = {
        "post": {"ok": True, "result": {"message_id": 1}},
    }
    telegram_mod.requests.post = lambda url, **kwargs: FakeResp(responses["post"])

    adapter = TelegramAdapter(TelegramConfig(bot_token="t"))
    ok = adapter.send("chat", "hello")
    assert ok is True


def test_discord_adapter_send():
    from prism.gateway.discord import DiscordAdapter, DiscordConfig
    import prism.gateway.discord as discord_mod

    responses = {
        "post": {"id": "1", "channel_id": "c", "content": "hello"},
    }
    discord_mod.requests.post = lambda url, **kwargs: FakeResp(responses["post"])

    adapter = DiscordAdapter(DiscordConfig(bot_token="t"))
    ok = adapter.send("c", "hello")
    assert ok is True


def test_feishu_adapter_send():
    from prism.gateway.feishu import FeishuAdapter, FeishuConfig
    import prism.gateway.feishu as feishu_mod

    responses = {
        "post": {
            "code": 0,
            "data": {"message_id": "1"},
        },
    }
    feishu_mod.requests.post = lambda url, **kwargs: FakeResp(responses["post"])

    adapter = FeishuAdapter(FeishuConfig(app_id="a", app_secret="s"))
    adapter.access_token = "fake_token"
    adapter.token_expires_at = 9999999999
    ok = adapter.send("chat", "hello")
    assert ok is True
