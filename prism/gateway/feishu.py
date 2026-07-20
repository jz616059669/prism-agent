"""
PRISM Agent - 飞书 Gateway 适配器（WebSocket 长连接）
整合 Hermes 的飞书 WebSocket 能力
"""

import asyncio
import json
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from lark_oapi import Client as LarkClient
from lark_oapi.api.im.v1 import (
    CreateImageRequest,
    CreateImageRequestBody,
    CreateMessageRequest,
    CreateMessageRequestBody,
    PatchMessageRequest,
    PatchMessageRequestBody,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)

from prism.logging import logger
import traceback
from lark_oapi.api.im.v1.model.p2_im_message_receive_v1 import (
    P2ImMessageReceiveV1,
)
from lark_oapi.api.contact.v3 import GetUserRequest
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as FeishuWSClient

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore[assignment]

try:
    import aiohttp
    from aiohttp import web
except ImportError:
    aiohttp = None  # type: ignore[assignment]
    web = None  # type: ignore[assignment]

from prism.gateway.base import PlatformAdapter, Message

try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]

requests = _requests


class FeishuEvent:
    def __init__(self, event_type: str, message: Dict[str, Any]):
        self.event_type = event_type
        self.message = message


FEISHU_WEBSOCKET_AVAILABLE = websockets is not None
FEISHU_WEBHOOK_AVAILABLE = aiohttp is not None


@dataclass
class FeishuConfig:
    app_id: str
    app_secret: str
    encrypt_key: Optional[str] = None
    verification_token: Optional[str] = None
    base_url: str = "https://open.feishu.cn/open-apis"


class FeishuAdapter(PlatformAdapter):
    platform = "feishu"

    def __init__(self, config: FeishuConfig):
        self.config = config
        self.handler: Optional[Callable[[Message], None]] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_client: Optional[FeishuWSClient] = None
        self.access_token: Optional[str] = None
        self.token_expires_at: int = 0

    def start_polling(self, handler: Callable[[Message], None]):
        """Compatibility alias for start()."""
        self.start(handler)

    def parse_event(self, body: Dict[str, Any]) -> Optional[Message]:
        """Parse feishu webhook payload to Message."""
        try:
            event = body.get("event", {})
            message = event.get("message", {})
            sender = event.get("sender", {})
            chat_id = message.get("chat_id", "")
            user_id = sender.get("sender_id", {}).get("open_id", "")
            text = ""
            if message.get("message_type") == "text":
                content = json.loads(message.get("content", "{}"))
                text = content.get("text", "")
            return Message(
                platform="feishu",
                chat_id=chat_id,
                user_id=user_id,
                text=text,
                raw=message,
            )
        except Exception as e:
            print(f"[Feishu] parse_event failed: {e}")
            return None

    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get user info via lark_oapi SDK."""
        try:
            client = LarkClient.builder() \
                .app_id(self.config.app_id) \
                .app_secret(self.config.app_secret) \
                .build()
            request = GetUserRequest.builder() \
                .user_id(user_id) \
                .user_id_type("open_id") \
                .build()
            response = client.contact.v3.user.get(request)
            if response.success():
                user = response.data.user if response.data and response.data.user else {}
                return {"success": True, "user": {"name": user.get("name", "")}}
            return {"success": False, "error": response.msg}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send(self, chat_id: str, text: str) -> bool:
        try:
            client = LarkClient.builder() \
                .app_id(self.config.app_id) \
                .app_secret(self.config.app_secret) \
                .build()
            body = CreateMessageRequestBody.builder() \
                .receive_id(chat_id) \
                .msg_type("text") \
                .content(json.dumps({"text": text}, ensure_ascii=False)) \
                .build()
            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(body) \
                .build()
            response = client.im.v1.message.create(request)
            if response.success():
                message_id = response.data.message_id if response.data and response.data.message_id else ""
                print(f"[Feishu] 消息已发送 -> {chat_id}")
                return message_id != ""
            else:
                print(f"[Feishu] 发送失败: code={response.code}, msg={response.msg}")
                return False
        except Exception as e:
            print(f"[Feishu] 发送消息异常: {e}")
            return False

    def send_thinking(self, chat_id: str, text: str = "正在修炼中……") -> Optional[str]:
        """发送一条“思考中”占位消息，返回 message_id 以便后续更新"""
        try:
            client = LarkClient.builder() \
                .app_id(self.config.app_id) \
                .app_secret(self.config.app_secret) \
                .build()
            body = CreateMessageRequestBody.builder() \
                .receive_id(chat_id) \
                .msg_type("text") \
                .content(json.dumps({"text": text}, ensure_ascii=False)) \
                .build()
            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(body) \
                .build()
            response = client.im.v1.message.create(request)
            if response.success() and response.data and response.data.message_id:
                return response.data.message_id
            return None
        except Exception as e:
            print(f"[Feishu] 发送思考状态失败: {e}")
            return None

    def update_message(self, message_id: str, text: str) -> bool:
        """替换已发送消息的内容，用于把“思考中”改成最终回复"""
        try:
            client = LarkClient.builder() \
                .app_id(self.config.app_id) \
                .app_secret(self.config.app_secret) \
                .build()
            body = PatchMessageRequestBody.builder() \
                .content(json.dumps({"text": text}, ensure_ascii=False)) \
                .build()
            request = PatchMessageRequest.builder() \
                .message_id(message_id) \
                .request_body(body) \
                .build()
            response = client.im.v1.message.patch(request)
            if response.success():
                return True
            else:
                print(f"[Feishu] 更新消息失败: code={response.code}, msg={response.msg}")
                return False
        except Exception as e:
            print(f"[Feishu] 更新消息异常: {e}")
            return False

    def start(self, handler: Callable[[Message], None]) -> bool:
        self.handler = handler
        self.running = True
        self._thread = threading.Thread(target=self._run_ws, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self.running = False
        if self._ws_client is not None:
            try:
                close = getattr(self._ws_client, "stop", None) or getattr(self._ws_client, "close", None)
                if close is not None:
                    if asyncio.iscoroutinefunction(close):
                        if self._loop and not self._loop.is_closed():
                            self._loop.run_until_complete(close())
                    else:
                        close()
            except Exception:
                logger.debug("feishu ws client close failed: %s", traceback.format_exc())
        if self._loop is not None and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                logger.debug("feishu loop stop failed: %s", traceback.format_exc())
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._ws_client = None
        self._loop = None
        self._thread = None
        self.handler = None
        print("[Feishu] 已停止")

    def _run_ws(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            try:
                import nest_asyncio
                nest_asyncio.apply(self._loop)
            except Exception:
                pass

            ws_client = FeishuWSClient(
                self.config.app_id,
                self.config.app_secret,
                event_handler=EventDispatcherHandler.builder("", "")
                .register_p2_im_message_receive_v1(
                    self._on_message_received,
                )
                .build(),
            )
            self._ws_client = ws_client
            self._loop.run_until_complete(ws_client.start())
        except Exception as e:
            print(f"[Feishu] WebSocket 启动失败: {e}")
            self.running = False

    def _on_message_received(self, event: P2ImMessageReceiveV1) -> None:
        try:
            message = getattr(event, 'event', event).message
            sender = getattr(event, 'event', event).sender
            chat_id = message.chat_id
            user_id = sender.sender_id.open_id if sender and sender.sender_id else ""
            text = ""
            if message.message_type == "text":
                content = json.loads(message.content or "{}")
                text = content.get("text", "")

            feishu_event = FeishuEvent(
                event_type="im.message.receive_v1",
                message={
                    "chat_id": chat_id,
                    "user_id": user_id,
                    "text": text,
                    "message_id": message.message_id,
                    "message_type": message.message_type,
                },
            )

            message_obj = Message(
                platform="feishu",
                chat_id=feishu_event.message.get("chat_id", ""),
                user_id=feishu_event.message.get("user_id", ""),
                text=feishu_event.message.get("text", ""),
                raw=feishu_event.message,
            )

            if self.handler:
                self.handler(message_obj)
        except Exception as e:
            print(f"[Feishu] 解析消息失败: {e}")
