"""
PRISM Agent - Trace Context 分布式追踪
跨 Agent/工具/LLM 的链路追踪，W3C traceparent 兼容
"""

from __future__ import annotations

import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_span_id: str = ""
    name: str = ""
    start: float = field(default_factory=time.time)
    end: float = 0.0
    status: str = "ok"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start": self.start,
            "end": self.end,
            "duration_ms": (self.end - self.start) * 1000.0,
            "status": self.status,
            "metadata": self.metadata,
        }


class Tracer:
    def __init__(self) -> None:
        self._spans: List[Span] = []

    def start_span(self, name: str, parent: Optional[Span] = None, metadata: Optional[Dict[str, Any]] = None) -> Span:
        span = Span(
            trace_id=parent.trace_id if parent else secrets.token_hex(16),
            span_id=secrets.token_hex(8),
            parent_span_id=parent.span_id if parent else "",
            name=name,
            metadata=metadata or {},
        )
        self._spans.append(span)
        return span

    def end_span(self, span: Span, status: str = "ok") -> None:
        span.end = time.time()
        span.status = status

    def spans(self, trace_id: Optional[str] = None) -> List[Dict[str, Any]]:
        spans = [s.to_dict() for s in self._spans if trace_id is None or s.trace_id == trace_id]
        return spans

    def to_w3c_traceparent(self, span: Optional[Span] = None) -> str:
        span = span or self._spans[-1] if self._spans else None
        if not span:
            return "00-" + "0" * 32 + "-" + "0" * 16 + "-01"
        return f"00-{span.trace_id}-{span.span_id}-01"


tracer = Tracer()
