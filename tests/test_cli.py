"""
PRISM Agent - CLI 测试
覆盖：version、doctor、config、skill、gateway status
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from click.testing import CliRunner
from prism.cli import cli


@pytest.fixture(scope="module")
def runner():
    return CliRunner()


def test_cli_version(runner):
    result = runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "2.1.2" in result.output


def test_cli_doctor(runner):
    result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 0
    assert "检查项" in result.output or "PRISM" in result.output


def test_cli_config_get(runner):
    result = runner.invoke(cli, ["config", "get"])
    assert result.exit_code == 0


def test_cli_skill_list(runner):
    result = runner.invoke(cli, ["skill", "list"])
    assert result.exit_code == 0
    assert "Skills" in result.output or "skill" in result.output.lower()


def test_cli_gateway_status(runner):
    result = runner.invoke(cli, ["gateway", "status"])
    assert result.exit_code == 0


def test_cli_tools(runner):
    result = runner.invoke(cli, ["tools"])
    assert result.exit_code == 0
    # 未配置模型时，tools 可能返回配置提示，至少应给出可读输出
    assert result.output and len(result.output.strip()) > 0


def test_cli_ask(runner, monkeypatch):
    fake_agent = type("FakeAgent", (), {"chat": lambda self, msg: "fake reply"})()
    monkeypatch.setattr("prism.cli.create_agent", lambda: fake_agent)
    result = runner.invoke(cli, ["ask", "hello"])
    assert result.exit_code == 0
    assert "hello" in result.output or "fake reply" in result.output or "PRISM" in result.output


def test_cli_chat_smoke(runner, monkeypatch):
    fake_agent = type("FakeAgent", (), {"chat": lambda self, msg: "fake reply", "clear_history": lambda self: None})()
    monkeypatch.setattr("prism.cli.create_agent", lambda: fake_agent)
    inputs = iter(["/exit"])
    monkeypatch.setattr("prism.cli.Prompt.ask", lambda *args, **kwargs: next(inputs))
    result = runner.invoke(cli, ["chat"])
    assert result.exit_code == 0
    assert "PRISM" in result.output or "再见" in result.output or "配置" in result.output
