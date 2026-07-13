"""
PRISM Agent - Event Bus 事件总线
模块间解耦通信，支持本地/跨进程
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_EVENT_DIR = Path.home() / ".prism" / "events"
_EVENT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Event:
    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    source: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "payload": self.payload,
            "ts": self.ts,
            "source": self.source,
        }


class EventBus:
    def __init__(self, persist: bool = True) -> None:
        self._handlers: Dict[str, List[Callable[[Event], None]]] = {}
        self._history: List[Event] = []
        self._persist = persist

    def on(self, name: str, handler: Callable[[Event], None]) -> None:
        self._handlers.setdefault(name, []).append(handler)

    def off(self, name: str, handler: Callable[[Event], None]) -> None:
        handlers = self._handlers.get(name, [])
        try:
            handlers.remove(handler)
        except ValueError:
            pass

    def emit(self, event: Event) -> None:
        self._history.append(event)
        if self._persist:
            try:
                with (_EVENT_DIR / "events.jsonl").open("a", encoding="utf-8") as f:
                    f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
            except Exception:
                pass
        for handler in self._handlers.get(event.name, []):
            try:
                handler(event)
            except Exception as exc:
                logger.debug("event handler failed: %s", exc)

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._history[-limit:]]


event_bus = EventBus()
