"""
PRISM Agent - WebSocket 客户端
原生 WS 协议支持
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WSMessage:
    type: str = "text"
    data: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "data": self.data,
        }


class WSClient:
    def __init__(self) -> None:
        self._messages: List[WSMessage] = []
        self._websocket = None

    def connect(self, url: str) -> bool:
        try:
            import websockets
            self._websocket = websockets.connect(url)
            return True
        except Exception:
            return False

    def send(self, data: str) -> bool:
        if not self._websocket:
            return False
        try:
            self._websocket.send(data)
            self._messages.append(WSMessage(type="sent", data=data))
            return True
        except Exception:
            return False

    def recv(self) -> Optional[str]:
        if not self._websocket:
            return None
        try:
            data = self._websocket.recv()
            self._messages.append(WSMessage(type="received", data=data))
            return data
        except Exception:
            return None

    def close(self) -> None:
        if self._websocket:
            try:
                self._websocket.close()
            except Exception:
                pass
            self._websocket = None

    def history(self) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self._messages]


ws_client = WSClient()
