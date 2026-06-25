"""Gateway 接收端真实连接测试（本地 HTTP + 线程）"""

import sys
import threading
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_feishu_webhook_server_local():
    from prism.gateway.feishu import FeishuAdapter, FeishuConfig

    received = {}

    def handler(msg):
        received['msg'] = msg

    adapter = FeishuAdapter(FeishuConfig(app_id="a", app_secret="s", encrypt_key=""))
    adapter.start_webhook(handler, host="127.0.0.1", port=18923)

    import urllib.request
    body = b'{"header":{"event_type":"im.message.receive_v1"},"event":{"message":{"chat_id":"oc123","message_type":"text","content":"{\\"text\\":\\"hello\\"}"},"sender":{"sender_id":{"open_id":"u123"}}}}'
    req = urllib.request.Request(
        "http://127.0.0.1:18923/webhook/feishu",
        data=body,
        headers={"Content-Type": "application/json", "X-Lark-Request-Timestamp": "1", "X-Lark-Request-Nonce": "1", "X-Lark-Signature": "bad"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass
    adapter.stop()

    assert 'msg' in received
    assert received['msg'].text == "hello"
    assert received['msg'].chat_id == "oc123"


def test_discord_start_polling_thread():
    from prism.gateway.discord import DiscordAdapter, DiscordConfig

    adapter = DiscordAdapter(DiscordConfig(bot_token="t"))
    called = {}

    def handler(msg):
        called['msg'] = msg

    adapter.start_polling(handler)
    assert adapter.running is True
    assert adapter.handler is handler
    adapter.stop()
    assert adapter.running is False


def test_telegram_webhook_server_local():
    from prism.gateway.telegram import TelegramAdapter, TelegramConfig

    received = {}

    def handler(msg):
        received['msg'] = msg

    adapter = TelegramAdapter(TelegramConfig(bot_token="t"))
    adapter.start_webhook(handler, host="127.0.0.1", port=18924)

    import urllib.request
    body = b'{"update_id":1,"message":{"message_id":10,"chat":{"id":99,"type":"private"},"from":{"id":77,"is_bot":false,"first_name":"User"},"text":"hello telegram"}}'
    req = urllib.request.Request(
        "http://127.0.0.1:18924/webhook/telegram",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass
    adapter.stop()

    assert 'msg' in received
    assert received['msg'].text == "hello telegram"
    assert received['msg'].chat_id == "99"
    assert received['msg'].platform == "telegram"
