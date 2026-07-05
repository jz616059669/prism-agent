"""
PRISM Agent - 统一 AI Agent CLI
整合 Hermes/Codex/OpenClaw 优势的新一代 AI Agent
"""

from pathlib import Path

__version__ = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()

from prism.agent import Agent, Message, ToolCall, create_agent

__all__ = [
    "__version__",
    "Agent",
    "Message",
    "ToolCall",
    "create_agent",
]
