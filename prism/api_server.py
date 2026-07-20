"""
PRISM Agent - API Server Mode
暴露 OpenAI-compatible HTTP endpoint，可被 Open WebUI / LibreChat 等前端直接调用。
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from typing import Any, Dict, List, Optional

from prism.logging import logger

try:
    from fastapi import FastAPI, Request  # type: ignore[import-untyped]
    from fastapi.responses import JSONResponse  # type: ignore[import-untyped]
    import uvicorn  # type: ignore[import-untyped]

    _FASTAPI_AVAILABLE = True
except Exception:  # noqa: BLE001
    FastAPI = None  # type: ignore[misc,assignment]
    Request = None  # type: ignore[misc,assignment]
    JSONResponse = None  # type: ignore[misc,assignment]
    uvicorn = None  # type: ignore[misc,assignment]
    _FASTAPI_AVAILABLE = False


try:
    from prism.agent import Agent, create_agent
    from prism.providers.manager import provider_pool
except Exception:  # noqa: BLE001
    Agent = None  # type: ignore[misc,assignment]
    create_agent = None  # type: ignore[misc,assignment]
    provider_pool = None  # type: ignore[misc,assignment]


_REQUEST_TIMEOUT = float(os.getenv("PRISM_API_REQUEST_TIMEOUT", "8"))

try:
    from prism import __version__ as _prism_version
except Exception:
    _prism_version = "2.1.6"


class PRISMApiServer:
    """
    轻量 OpenAI-compatible HTTP 服务：
    - POST /v1/chat/completions
    - GET  /v1/models
    - GET  /health
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        agent_factory: Optional[Any] = None,
    ) -> None:
        if not _FASTAPI_AVAILABLE:
            raise RuntimeError("fastapi/uvicorn 未安装，无法启动 API 服务")
        self.host = host
        self.port = port
        self._agent_factory = agent_factory or self._default_factory
        self._app = FastAPI(title="PRISM Agent API", version=_prism_version)
        self._server_thread: Optional[threading.Thread] = None
        self._running = False
        self._register_routes()

    def _default_factory(self, session_id: str = "") -> Any:
        if create_agent is None:
            raise RuntimeError("PRISM agent not initialized")
        agent = create_agent()
        agent.session_id = session_id
        return agent

    def _register_routes(self) -> None:
        app = self._app

        @app.get("/health")
        async def health() -> JSONResponse:
            return JSONResponse({"status": "ok", "version": _prism_version})

        @app.get("/v1/models")
        async def list_models(request: Request) -> JSONResponse:
            try:
                names: List[str] = []
                if provider_pool is not None:
                    try:
                        names = provider_pool.list_providers()
                    except Exception:
                        names = []
                data = {
                    "object": "list",
                    "data": [
                        {"id": name, "object": "model", "owned_by": "prism"}
                        for name in names
                    ],
                }
                return JSONResponse(data)
            except Exception as exc:
                logger.debug("list models failed: %s", exc)
                return JSONResponse({"error": str(exc)}, status_code=500)

        @app.post("/v1/chat/completions")
        async def chat_completions(request: Request) -> JSONResponse:
            try:
                body = await request.json()
                messages = body.get("messages") or []
                user_content = ""
                if messages:
                    last = messages[-1]
                    user_content = last.get("content") or ""
                    if isinstance(user_content, list):
                        user_content = " ".join(
                            part.get("text", "") for part in user_content if isinstance(part, dict)
                        )
                stream = bool(body.get("stream", False))
                if stream:
                    return JSONResponse(
                        {"error": {"message": "stream is not supported in this build", "type": "invalid_request_error"}},
                        status_code=400,
                    )
                sid = body.get("session_id") or body.get("user") or "api"
                agent = self._agent_factory(session_id=sid)
                try:
                    response_text = await asyncio.wait_for(
                        asyncio.get_running_loop().run_in_executor(None, agent.chat, user_content or ""),
                        timeout=_REQUEST_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    return JSONResponse(
                        {"error": {"message": f"request timeout after {_REQUEST_TIMEOUT}s", "type": "timeout_error"}},
                        status_code=504,
                    )
                data = {
                    "id": f"chatcmpl-{sid}",
                    "object": "chat.completion",
                    "model": getattr(agent, "model", "") or "",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": response_text},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": 0,
                    },
                }
                return JSONResponse(data)
            except Exception as exc:
                logger.debug("chat completions failed: %s", exc)
                return JSONResponse(
                    {"error": {"message": str(exc), "type": "prism_error"}},
                    status_code=500,
                )

    def start(self, background: bool = True) -> Optional[threading.Thread]:
        if self._running:
            return None
        self._running = True
        if not background:
            uvicorn.run(self._app, host=self.host, port=self.port, log_level="warning")
            return None
        t = threading.Thread(
            target=lambda: uvicorn.run(self._app, host=self.host, port=self.port, log_level="warning"),
            daemon=True,
        )
        t.start()
        self._server_thread = t
        return t

    def stop(self) -> None:
        self._running = False

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"


__all__ = ["PRISMApiServer"]

