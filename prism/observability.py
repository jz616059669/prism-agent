"""
PRISM Agent - Web 可观测面板
本地 Flask 实时看 traces/metrics/logs
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_OBS_DIR = Path.home() / ".prism" / "observability"
_OBS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class Trace:
    ts: float
    trace_id: str
    span: str
    duration_ms: float = 0.0
    status: str = "ok"
    metadata: Dict[str, Any] = field(default_factory=dict)


class ObservabilityStore:
    def __init__(self, max_traces: int = 1000) -> None:
        self._traces: List[Trace] = []
        self._max_traces = max_traces

    def record_trace(self, trace: Trace) -> None:
        self._traces.append(trace)
        if len(self._traces) > self._max_traces:
            self._traces = self._traces[-self._max_traces:]

    def recent_traces(self, n: int = 50) -> List[Dict[str, Any]]:
        return [t.__dict__ for t in self._traces[-n:]]

    def summary(self) -> Dict[str, Any]:
        total = len(self._traces)
        errors = sum(1 for t in self._traces if t.status != "ok")
        avg_duration = sum(t.duration_ms for t in self._traces) / total if total else 0.0
        return {
            "total_traces": total,
            "errors": errors,
            "error_rate": round(errors / total * 100, 1) if total else 0.0,
            "avg_duration_ms": round(avg_duration, 1),
        }


observability = ObservabilityStore()


def _start_flask_app() -> None:
    try:
        from flask import Flask, jsonify, render_template_string

        app = Flask(__name__)

        @app.route("/")
        def index():
            return render_template_string("""
<!DOCTYPE html>
<html>
<head><title>PRISM Observability</title></head>
<body>
<h1>PRISM Observability</h1>
<h2>Summary</h2>
<pre id="summary"></pre>
<h2>Recent Traces</h2>
<pre id="traces"></pre>
<script>
fetch('/api/summary').then(r=>r.json()).then(d=>document.getElementById('summary').textContent=JSON.stringify(d,null,2));
fetch('/api/traces').then(r=>r.json()).then(d=>document.getElementById('traces').textContent=JSON.stringify(d,null,2));
</script>
</body>
</html>
""")

        @app.route("/api/summary")
        def api_summary():
            return jsonify(observability.summary())

        @app.route("/api/traces")
        def api_traces():
            return jsonify(observability.recent_traces())

        port = int(os.environ.get("PRISM_OBS_PORT", "8765"))
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    except Exception as exc:
        logger.warning("observability panel failed: %s", exc)


def start_observability_panel() -> None:
    try:
        import threading
        t = threading.Thread(target=_start_flask_app, daemon=True)
        t.start()
    except Exception:
        pass
