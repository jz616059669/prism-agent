"""
PRISM Agent - Web Remote Console
本地 Flask 控制台：手机/平板/其他设备可远程查看 Agent 状态、发起对话
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("prism.web_console")

try:
    from flask import Flask, jsonify, render_template_string, request  # type: ignore[import-untyped]

    _FLASK_AVAILABLE = True
except Exception:  # noqa: BLE001
    Flask = None  # type: ignore[misc,assignment]
    _FLASK_AVAILABLE = False


class WebConsole:
    """轻量本地 Web 控制台，零前端构建依赖。"""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        agent_factory: Optional[Any] = None,
    ) -> None:
        if not _FLASK_AVAILABLE:
            raise RuntimeError("flask 未安装，无法启动 Web 控制台。请执行 `pip install flask`。")
        self.host = host
        self.port = int(port)
        self._agent_factory = agent_factory or self._default_factory
        self._app = Flask(__name__, template_folder=str(Path(__file__).resolve().parent / "templates"))
        self._server_thread: Optional[threading.Thread] = None
        self._running = False
        self._register_routes()

    def _default_factory(self, session_id: str = "") -> Any:
        try:
            from prism.agent import create_agent
        except Exception as exc:
            raise RuntimeError("PRISM agent not initialized") from exc
        agent = create_agent()
        agent.session_id = session_id or "web"
        return agent

    def _register_routes(self) -> None:
        app = self._app

        @app.get("/")
        def index():
            return render_template_string(INDEX_HTML)

        @app.get("/api/health")
        def health():
            return jsonify({"status": "ok", "version": "2.1.5"})

        @app.get("/api/sessions")
        def list_sessions():
            try:
                from prism.agent import Agent
                sessions = Agent.list_sessions()
                return jsonify({"sessions": sessions})
            except Exception as exc:
                logger.debug("list sessions failed: %s", exc)
                return jsonify({"sessions": []})

        @app.post("/api/chat")
        def chat():
            try:
                body = request.get_json(force=True) or {}
                message = (body.get("message") or "").strip()
                session_id = (body.get("session_id") or body.get("user") or "web").strip()
                if not message:
                    return jsonify({"error": "message is required"}), 400
                agent = self._agent_factory(session_id=session_id)
                response = agent.chat(message)
                return jsonify({"session_id": session_id, "response": response})
            except Exception as exc:
                logger.debug("web chat failed: %s", exc)
                return jsonify({"error": str(exc)}), 500

    def start(self, background: bool = True) -> Optional[threading.Thread]:
        if self._running:
            return None
        self._running = True
        if not background:
            self._app.run(host=self.host, port=self.port, debug=False, use_reloader=False)
            return None
        t = threading.Thread(
            target=lambda: self._app.run(host=self.host, port=self.port, debug=False, use_reloader=False),
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


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PRISM Web Console</title>
<style>
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body { margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }
.header { padding: 14px 18px; border-bottom: 1px solid #ccc; display: flex; justify-content: space-between; align-items: center; }
.title { font-weight: 700; font-size: 18px; }
.meta { opacity: .8; font-size: 12px; }
.chat { padding: 14px; height: calc(100dvh - 126px); overflow: auto; }
.bubble { max-width: 82%; padding: 10px 12px; border-radius: 14px; margin: 8px 0; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
.user { margin-left: auto; background: #2563eb; color: white; border-bottom-right-radius: 4px; }
.assistant { margin-right: auto; background: #e5e7eb; color: #0f172a; border-bottom-left-radius: 4px; }
.footer { padding: 10px 14px; border-top: 1px solid #ccc; display: flex; gap: 8px; }
input { flex: 1; padding: 10px 12px; border-radius: 12px; border: 1px solid #aaa; font-size: 16px; }
button { padding: 10px 14px; border-radius: 12px; border: 0; background: #2563eb; color: white; font-weight: 600; }
@media (prefers-color-scheme: dark) {
  .assistant { background: #1f2937; color: #e5e7eb; }
  body { background: #0b1220; color: #e5e7eb; }
}
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="title">PRISM Web Console</div>
    <div class="meta">会话复用: 同一个 session_id 共享上下文</div>
  </div>
  <div class="meta" id="status">就绪</div>
</div>
<div class="chat" id="chat"></div>
<div class="footer">
  <input id="message" placeholder="输入消息..." autocomplete="off">
  <button onclick="send()">发送</button>
</div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('message');
const status = document.getElementById('status');
const session_id = location.hash.replace('#','') || 'web';

function append(role, text) {
  const div = document.createElement('div');
  div.className = 'bubble ' + role;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

async function send() {
  const text = input.value.trim();
  if (!text) return;
  append('user', text);
  input.value = '';
  status.textContent = '思考中...';
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text, session_id})
    });
    const data = await res.json();
    if (data.response) append('assistant', data.response);
    else append('assistant', '[错误] ' + (data.error || 'unknown'));
  } catch (e) {
    append('assistant', '[网络错误] ' + e.message);
  } finally {
    status.textContent = '就绪';
  }
}

input.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });
</script>
</body>
</html>
"""


__all__ = ["WebConsole"]
