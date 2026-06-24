"""
PRISM Agent - 会话持久化测试
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.agent import create_agent


def test_session_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    agent = create_agent()
    agent.chat("hello")
    path = agent.save_session("s1")
    assert Path(path).exists()
    agent2 = create_agent()
    ok = agent2.load_session("s1")
    assert ok
    assert any(m.content == "hello" for m in agent2.messages if m.role == "user")


def test_session_list_and_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    agent = create_agent()
    agent.save_session("a")
    agent.save_session("b")
    assert "a" in agent.list_sessions()
    assert "b" in agent.list_sessions()
    assert agent.delete_session("a") is True
    assert "a" not in agent.list_sessions()
