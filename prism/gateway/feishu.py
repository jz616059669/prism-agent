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
    ReplyMessageRequest,
    ReplyMessageRequestBody,
)
from lark_oapi.event.callback.model.p2_im_message_message_read_v1 import (
    P2ImMessageMessageReadV1,
)
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as FeishuWSClient


class FeishuEvent:
    def __init__(self, event_type: str, message: Dict[str, Any]):
        self.event_type = event_type
        self.message = message


class FeishuConfig:
    app_id: str
    app_secret: str
    encrypt_key: Optional[str] = None
    verification_token: Optional[str] = None
    base_url: str = "https://open.feishu.cn/open-apis"


class FeishuAdapter:
    """
    飞书适配器（WebSocket 长连接模式）
    支持：
    - 接收消息（WebSocket）
    - 发送消息
    """

    platform = "feishu"

    def __init__(self, config: FeishuConfig):
        self.config = config
        self.handler: Optional[Callable[[FeishuEvent], None]] = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_client: Optional[FeishuWSClient] = None

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
                print(f"[Feishu] 消息已发送 -> {chat_id}")
                return True
            else:
                print(f"[Feishu] 发送失败: code={response.code}, msg={response.msg}")
                return False
        except Exception as e:
            print(f"[Feishu] 发送消息异常: {e}")
            return False

    def start(self, handler: Callable[[FeishuEvent], None]) -> bool:
        self.handler = handler
        self.running = True
        self._thread = threading.Thread(target=self._run_ws, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self.running = False
        if self._ws_client is not None:
            try:
                self._ws_client.stop()
            except Exception:
                pass
        if self._loop is not None and not self._loop.is_closed():
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._ws_client = None
        self._loop = None
        self._thread = None
        print("[Feishu] 已停止")

    def _run_ws(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            ws_client = FeishuWSClient(
                self.config.app_id,
                self.config.app_secret,
                event_handler=EventDispatcherHandler.builder("", "")
                .register_p2_im_message_message_read_v1(
                    P2ImMessageMessageReadV1,
                    self._on_message_received,
                )
                .build(),
            )
            self._ws_client = ws_client
            ws_client.start()
        except Exception as e:
            print(f"[Feishu] WebSocket 启动失败: {e}")
            self.running = False

    def _on_message_received(self, event: P2ImMessageMessageReadV1) -> None:
        try:
            message = event.event.message
            sender = event.event.sender
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

            if self.handler:
                self.handler(feishu_event)
        except Exception as e:
            print(f"[Feishu] 解析消息失败: {e}")
