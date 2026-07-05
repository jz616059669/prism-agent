"""Gateway 平台适配器真实连接测试（monkeypatch HTTP）"""

import sys
from pathlib import Path

import pytest
import threading

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
    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_response.success.return_value = True
    mock_response.code = 0
    mock_response.msg = "ok"

    mock_client = MagicMock()
    mock_client.im.v1.message.create.return_value = mock_response

    from unittest.mock import patch
    with patch("prism.gateway.feishu.LarkClient") as MockClient:
        MockClient.builder.return_value.app_id.return_value.app_secret.return_value.build.return_value = mock_client
        adapter = FeishuAdapter(FeishuConfig(app_id="a", app_secret="s"))
        ok = adapter.send("chat", "hello")
        assert ok is True


def test_feishu_ws_handler_converts_to_message():
    from prism.gateway.feishu import FeishuAdapter, FeishuConfig, FeishuEvent
    from unittest.mock import MagicMock

    received = {}
    def handler(msg):
        received["msg"] = msg

    adapter = FeishuAdapter(FeishuConfig(app_id="a", app_secret="s"))
    adapter.handler = handler

    event = MagicMock()
    event.event.message.chat_id = "oc123"
    event.event.message.message_type = "text"
    event.event.message.content = '{"text":"hello"}'
    event.event.message.message_id = "m123"
    event.event.sender.sender_id.open_id = "u123"

    adapter._on_message_received(event)

    msg = received["msg"]
    assert msg.platform == "feishu"
    assert msg.chat_id == "oc123"
    assert msg.user_id == "u123"
    assert msg.text == "hello"


def test_feishu_adapter_lifecycle():
    from prism.gateway.feishu import FeishuAdapter, FeishuConfig

    adapter = FeishuAdapter(FeishuConfig(app_id="a", app_secret="s"))
    adapter.start_polling(lambda msg: None)
    assert adapter.running is True
    assert adapter.handler is not None
    adapter.stop()
    assert adapter.running is False


def test_telegram_handle_update():
    from prism.gateway.telegram import TelegramAdapter, TelegramConfig

    adapter = TelegramAdapter(TelegramConfig(bot_token="t"))
    called = {}

    def handler(msg):
        called["msg"] = msg

    adapter.handler = handler
    update = {
        "update_id": 1,
        "message": {
            "chat": {"id": 1},
            "from": {"id": 2},
            "text": "hi",
        },
    }
    adapter._handle_update(update)
    assert called["msg"].text == "hi"
    assert called["msg"].chat_id == "1"


def test_discord_get_current_user():
    from prism.gateway.discord import DiscordAdapter, DiscordConfig
    import prism.gateway.discord as discord_mod

    discord_mod.requests.get = lambda url, **kwargs: FakeResp({"id": "1", "username": "bot"})
    adapter = DiscordAdapter(DiscordConfig(bot_token="t"))
    result = adapter.get_current_user()
    assert result.get("success") is True
    assert result.get("user", {}).get("username") == "bot"


def test_gateway_register_and_send():
    from prism.gateway import Gateway
    from prism.gateway.telegram import TelegramAdapter, TelegramConfig
    from prism.gateway.discord import DiscordAdapter, DiscordConfig
    import prism.gateway.discord as discord_mod
    import prism.gateway.telegram as telegram_mod

    discord_mod.requests.post = lambda url, **kwargs: FakeResp({"id": "1"})
    telegram_mod.requests.post = lambda url, **kwargs: FakeResp({"ok": True})

    gateway = Gateway()
    gateway.register("telegram", TelegramAdapter(TelegramConfig(bot_token="t")))
    gateway.register("discord", DiscordAdapter(DiscordConfig(bot_token="t")))

    assert set(gateway.list_platforms()) >= {"telegram", "discord"}
    assert gateway.send("telegram", "1", "hi") is True
    assert gateway.send("discord", "2", "hi") is True
    assert gateway.send("unknown", "1", "hi") is False


def test_gateway_start_stop_lifecycle(monkeypatch):
    from prism.gateway import Gateway
    from prism.gateway.feishu import FeishuAdapter, FeishuConfig

    started = []
    stopped = []

    class FakeAdapter:
        def __init__(self, name):
            self.name = name
            self.handler = None
            self.running = False

        def start_polling(self, handler):
            self.handler = handler
            self.running = True
            started.append(self.name)

        def stop(self):
            self.running = False
            self.handler = None
            stopped.append(self.name)

        def send(self, chat_id, text):
            return True

    gateway = Gateway()
    gateway.register("feishu", FakeAdapter("feishu"))
    gateway.register("telegram", FakeAdapter("telegram"))

    received = {}

    def handler(msg):
        received["msg"] = msg

    gateway.start(handler)

    assert started == ["feishu", "telegram"]
    assert gateway.running is True
    assert gateway.adapters["feishu"].running is True
    assert gateway.adapters["feishu"].handler is handler

    gateway.stop()
    assert stopped == ["feishu", "telegram"]
    assert gateway.running is False
    assert gateway.adapters["feishu"].running is False


def test_feishu_adapter_get_user_info():
    from prism.gateway.feishu import FeishuAdapter, FeishuConfig
    from unittest.mock import MagicMock, patch

    mock_response = MagicMock()
    mock_response.success.return_value = True
    mock_response.data.user = {"name": "user1"}

    mock_client = MagicMock()
    mock_client.contact.v3.user.get.return_value = mock_response

    with patch("prism.gateway.feishu.LarkClient") as MockClient:
        MockClient.builder.return_value.app_id.return_value.app_secret.return_value.build.return_value = mock_client
        adapter = FeishuAdapter(FeishuConfig(app_id="a", app_secret="s"))
        result = adapter.get_user_info("ou123")
        assert result.get("success") is True
        assert result.get("user", {}).get("name") == "user1"


def test_wechat_adapter_send(monkeypatch):
    from prism.gateway.wechat import WechatAdapter, WechatConfig
    import prism.gateway.wechat as wechat_mod

    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["token_url"] = url
        captured["params"] = params
        return FakeResp({"errcode": 0, "access_token": "fake_token"})

    def fake_post(url, params=None, json=None, timeout=None):
        captured["send_url"] = url
        captured["send_params"] = params
        captured["send_json"] = json
        return FakeResp({"errcode": 0})

    import requests as _requests
    monkeypatch.setattr(_requests, "get", fake_get)
    monkeypatch.setattr(_requests, "post", fake_post)

    adapter = WechatAdapter(WechatConfig(corp_id="c", agent_id="1", secret="s"))
    ok = adapter.send("user1", "hello")
    assert ok is True
    assert captured["send_params"].get("access_token") == "fake_token"
    assert captured["send_json"].get("touser") == "user1"


def test_wechat_start_polling_raises_not_implemented():
    from prism.gateway.wechat import WechatAdapter, WechatConfig

    adapter = WechatAdapter(WechatConfig(corp_id="c", agent_id="1", secret="s"))
    with pytest.raises(NotImplementedError):
        adapter.start_polling(lambda msg: None)


def test_adapter_lifecycle_sync(monkeypatch):
    import time
    import threading
    from unittest.mock import patch
    from prism.gateway.telegram import TelegramAdapter, TelegramConfig
    from prism.gateway.discord import DiscordAdapter, DiscordConfig
    from prism.gateway.feishu import FeishuAdapter, FeishuConfig

    import prism.gateway.telegram as telegram_mod

    def _fake_get(url, params=None, timeout=None):
        return FakeResp({"ok": True, "result": []})

    monkeypatch.setattr(telegram_mod.requests, "get", _fake_get)

    telegram = TelegramAdapter(TelegramConfig(bot_token="t"))
    t = threading.Thread(target=telegram.start_polling, args=(lambda msg: None,))
    t.start()
    time.sleep(0.05)
    assert telegram.running is True
    telegram.stop()
    assert telegram.running is False
    t.join(timeout=3)

    import prism.gateway.discord as discord_mod
    import sys
    discord_mod.websockets = sys.modules.get("websockets") or type(sys)("websockets")

    with patch("prism.gateway.discord.websockets") as mock_ws:
        mock_ws.connect.return_value.__enter__ = lambda self: self
        mock_ws.connect.return_value.__exit__ = lambda self, *args: None
        mock_ws.connect.return_value.recv.return_value = '{"op":10,"d":{"heartbeat_interval":45000}}'

        discord = DiscordAdapter(DiscordConfig(bot_token="t"))
        discord.start_polling(lambda msg: None)
        assert discord.running is True
        assert discord.handler is not None
        discord.stop()
        assert discord.running is False
        assert discord.handler is None

    feishu = FeishuAdapter(FeishuConfig(app_id="a", app_secret="s"))
    feishu.start_polling(lambda msg: None)
    assert feishu.running is True
    assert feishu.handler is not None
    feishu.stop()
    assert feishu.running is False
    assert feishu.handler is None

