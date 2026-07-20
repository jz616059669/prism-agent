"""
PRISM Agent - 轻量级可观测性
工具调用与 agent 行为的 trace 日志。
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("prism.observability")

_TRACE_DIR = Path.home() / ".prism" / "traces"
_TRACE_DIR.mkdir(parents=True, exist_ok=True)


def trace_tool(name: str):
    """工具调用耗时/结果 trace 装饰器"""
    def decorator(fn: Callable[..., Dict[str, Any]]) -> Callable[..., Dict[str, Any]]:
        def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            start = time.time()
            try:
                result = fn(*args, **kwargs)
                latency_ms = int((time.time() - start) * 1000)
                logger.debug(
                    "trace tool=%s latency=%dms success=%s",
                    name,
                    latency_ms,
                    result.get("success"),
                )
                try:
                    _append_trace({
                        "ts": datetime.now().isoformat(),
                        "type": "tool",
                        "name": name,
                        "args": _safe_args(kwargs),
                        "success": result.get("success"),
                        "error": result.get("error"),
                        "latency_ms": latency_ms,
                    })
                except Exception:
                    pass
                return result
            except Exception as exc:
                latency_ms = int((time.time() - start) * 1000)
                logger.debug("trace tool=%s latency=%dms error=%s", name, latency_ms, exc)
                try:
                    _append_trace({
                        "ts": datetime.now().isoformat(),
                        "type": "tool",
                        "name": name,
                        "args": _safe_args(kwargs),
                        "success": False,
                        "error": str(exc),
                        "latency_ms": latency_ms,
                    })
                except Exception:
                    pass
                raise
        return wrapper
    return decorator


def _safe_args(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """脱敏敏感参数"""
    out = {}
    for k, v in kwargs.items():
        if any(s in k.lower() for s in ["secret", "token", "password", "api_key"]):
            out[k] = "***"
        else:
            out[k] = v
    return out


def _append_trace(record: Dict[str, Any]) -> None:
    path = _TRACE_DIR / f"{datetime.now().strftime('%Y%m%d')}.jsonl"
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
