"""
PRISM Agent - 多模态输出
输出图表/音频/文件，不只是文本回复
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_OUT_DIR = Path.home() / ".prism" / "output"
_OUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class MultimodalOutput:
    content_type: str = "text"
    content: str = ""
    path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content_type": self.content_type,
            "content": self.content,
            "path": self.path,
            "metadata": self.metadata,
        }


class MultimodalOutputEngine:
    def text(self, content: str) -> MultimodalOutput:
        return MultimodalOutput(content_type="text", content=content)

    def chart(self, data: List[Dict[str, Any]], kind: str = "bar") -> MultimodalOutput:
        out = MultimodalOutput(content_type="chart")
        try:
            import matplotlib.pyplot as plt
            import base64
            from io import BytesIO
            fig, ax = plt.subplots()
            if kind == "bar":
                labels = [str(d.get("label", "")) for d in data]
                values = [float(d.get("value", 0)) for d in data]
                ax.bar(labels, values)
            elif kind == "line":
                xs = [float(d.get("x", 0)) for d in data]
                ys = [float(d.get("y", 0)) for d in data]
                ax.plot(xs, ys)
            buf = BytesIO()
            fig.savefig(buf, format="png", dpi=100)
            buf.seek(0)
            b64 = base64.b64encode(buf.read()).decode("utf-8")
            out.metadata["base64"] = b64
            plt.close(fig)
        except Exception as exc:
            logger.debug("chart render failed: %s", exc)
        return out

    def file(self, filename: str, content: str) -> MultimodalOutput:
        path = str(_OUT_DIR / filename)
        try:
            Path(path).write_text(content, encoding="utf-8")
        except Exception:
            pass
        return MultimodalOutput(content_type="file", path=path)


multimodal_output = MultimodalOutputEngine()
