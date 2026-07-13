"""
PRISM Agent - Async Compatibility Layer
轻量 async 兼容层，允许 async 调用现有 sync 方法
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from typing import Any, Callable, Coroutine, Dict, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def to_async(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """将 sync 方法包装为 async，不修改原实现。"""
    if inspect.iscoroutinefunction(func):
        return func

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))

    return wrapper


class AsyncCompatibility:
    """全局 async 兼容标记。为后续全链路 async 预留。"""
    enabled: bool = False
    _wrapped: Dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}

    @classmethod
    def wrap(cls, name: str, func: Callable[..., Any]) -> Callable[..., Coroutine[Any, Any, Any]]:
        if name in cls._wrapped:
            return cls._wrapped[name]
        wrapped = to_async(func)
        cls._wrapped[name] = wrapped
        return wrapped

    @classmethod
    def enable(cls) -> None:
        cls.enabled = True
        logger.info("async compatibility enabled")

    @classmethod
    def disable(cls) -> None:
        cls.enabled = False
        logger.info("async compatibility disabled")
