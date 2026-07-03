"""
PRISM Agent - 统一 AI Agent CLI
整合 Hermes/Codex/OpenClaw 优势的新一代 AI Agent
"""

__version__ = "2.1.2"

from prism.agent import Agent, Message, ToolCall, create_agent

__all__ = [
    "__version__",
    "Agent",
    "Message",
    "ToolCall",
    "create_agent",
]
