"""
PRISM Agent - Orchestrator tests
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from prism.agent import Agent
from prism.orchestrator import TaskOrchestrator, RoleAgent


def test_role_agent_unknown_role():
    with pytest.raises(ValueError):
        RoleAgent(role="invalid")


def test_role_agent_run():
    parent = Agent()
    parent.session_id = "tests"
    parent._persist_disabled = True
    parent._session_json_enabled = False
    r = RoleAgent(role="researcher", parent_context="ctx")
    with patch("prism.providers.manager.provider_pool.chat", return_value={"success": True, "content": "mock"}):
        out = r.run("hello")
    assert isinstance(out, str)
    assert len(out) > 0


def test_detect_roles_empty():
    o = TaskOrchestrator()
    assert o._detect_roles("") == []
    assert o._detect_roles("你好") == []


def test_detect_roles_coder_and_writer():
    o = TaskOrchestrator()
    roles = o._detect_roles("帮我写代码实现一个小工具，并写成文档")
    assert "coder" in roles
    assert "writer" in roles


def test_orchestrator_single_role_delegates():
    parent = Agent()
    parent.session_id = "tests"
    parent._persist_disabled = True
    parent._session_json_enabled = False
    o = TaskOrchestrator()
    with patch("prism.providers.manager.provider_pool.chat", return_value={"success": True, "content": "mock output"}):
        out = o.orchestrate("请检索一下 Rust 语言的特点", parent)
    assert isinstance(out, str)
    assert len(out) > 0


def test_orchestrator_multi_role_synthesis():
    parent = Agent()
    parent.session_id = "tests"
    parent._persist_disabled = True
    parent._session_json_enabled = False
    o = TaskOrchestrator()
    task = "请调研 Rust 语言特点，然后写一篇介绍文档，并检查是否有逻辑问题"
    with patch("prism.providers.manager.provider_pool.chat", return_value={"success": True, "content": "mock synthesis"}):
        out = o.orchestrate(task, parent)
    assert isinstance(out, str)
    assert len(out) > 0
    assert "【多 Agent 执行结果】" in out or "mock synthesis" in out


def test_orchestrator_max_parallel_limit():
    o = TaskOrchestrator(max_parallel=2)
    text = "调研 Rust，写代码，审阅，撰写文档"
    roles = o._detect_roles(text)
    assert len(roles) <= 2
