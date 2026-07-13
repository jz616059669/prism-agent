"""
PRISM Agent - 性能火焰图
可视化函数调用耗时，本地 SVG 导出
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_FLAME_DIR = Path.home() / ".prism" / "flame"
_FLAME_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class FlameFrame:
    name: str
    start_ms: float = 0.0
    duration_ms: float = 0.0
    depth: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "start_ms": self.start_ms,
            "duration_ms": self.duration_ms,
            "depth": self.depth,
        }


class FlameGraph:
    def __init__(self) -> None:
        self._frames: List[FlameFrame] = []

    def record(self, name: str, start_ms: float, duration_ms: float, depth: int = 0) -> None:
        self._frames.append(FlameFrame(name=name, start_ms=start_ms, duration_ms=duration_ms, depth=depth))

    def to_svg(self, width: int = 1200, height: int = 600) -> str:
        if not self._frames:
            return "<svg></svg>"
        bar_h = 18
        y_gap = 2
        max_end = max(f.start_ms + f.duration_ms for f in self._frames) or 1.0
        x_scale = (width - 120) / max_end
        lines = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' style='background:#1e1e1e'>"]
        for frame in self._frames:
            x = 100 + frame.start_ms * x_scale
            w = max(2.0, frame.duration_ms * x_scale)
            y = 20 + frame.depth * (bar_h + y_gap)
            lines.append(f"<rect x='{x}' y='{y}' width='{w}' height='{bar_h}' rx='3' fill='#ffab40' opacity='0.9'/>")
            lines.append(f"<text x='{x + 4}' y='{y + 12}' fill='#fff' font-size='10' font-family='monospace'>{frame.name}</text>")
        lines.append("</svg>")
        return "\n".join(lines)

    def export_svg(self, filename: str = "flame.svg") -> str:
        out = str(_FLAME_DIR / filename)
        try:
            Path(out).write_text(self.to_svg(), encoding="utf-8")
        except Exception:
            pass
        return out


flame_graph = FlameGraph()
