"""
PRISM Agent - 统一 AI Agent CLI
整合 Hermes/Codex/OpenClaw 优势的新一代 AI Agent
"""

from pathlib import Path
import sys

if getattr(sys, 'frozen', False):
    _base = Path(sys._MEIPASS)
else:
    _base = Path(__file__).resolve().parents[1]

_version_path = _base / "VERSION"
if _version_path.exists():
    __version__ = _version_path.read_text(encoding="utf-8").strip()
else:
    __version__ = "2.1.3"

from prism.agent import Agent, Message, ToolCall, create_agent

__all__ = [
    "__version__",
    "Agent",
    "Message",
    "ToolCall",
    "create_agent",
]
