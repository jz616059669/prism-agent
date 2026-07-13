"""
PRISM Agent - 多模态输入
图片/音频/文件直接输入对话
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MultimodalInput:
    type: str = "text"  # text | image | audio | file
    content: str = ""
    mime: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "content": self.content,
            "mime": self.mime,
        }


class MultimodalInputEngine:
    def text(self, content: str) -> MultimodalInput:
        return MultimodalInput(type="text", content=content)

    def image(self, path: str) -> MultimodalInput:
        p = Path(path)
        if not p.exists():
            return MultimodalInput(type="image", content="", mime="")
        try:
            data = base64.b64encode(p.read_bytes()).decode("ascii")
            return MultimodalInput(type="image", content=f"data:image/png;base64,{data}", mime="image/png")
        except Exception:
            return MultimodalInput(type="image", content="", mime="")

    def audio(self, path: str) -> MultimodalInput:
        p = Path(path)
        if not p.exists():
            return MultimodalInput(type="audio", content="", mime="")
        try:
            data = base64.b64encode(p.read_bytes()).decode("ascii")
            return MultimodalInput(type="audio", content=f"data:audio/wav;base64,{data}", mime="audio/wav")
        except Exception:
            return MultimodalInput(type="audio", content="", mime="")

    def file(self, path: str) -> MultimodalInput:
        p = Path(path)
        if not p.exists():
            return MultimodalInput(type="file", content="", mime="")
        try:
            data = base64.b64encode(p.read_bytes()).decode("ascii")
            return MultimodalInput(type="file", content=data, mime="application/octet-stream")
        except Exception:
            return MultimodalInput(type="file", content="", mime="")


multimodal_input = MultimodalInputEngine()
