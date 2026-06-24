"""
PRISM Agent - Session CLI 测试
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


@pytest.fixture
def runner():
    return CliRunner()


def test_session_list_empty(runner):
    result = runner.invoke(cli, ["session", "list"])
    assert result.exit_code == 0
    assert "会话" in result.output or "暂无" in result.output


def test_session_save_and_load(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    result = runner.invoke(cli, ["session", "save", "s1"])
    assert result.exit_code == 0
    assert "已保存" in result.output
    result = runner.invoke(cli, ["session", "load", "s1"])
    assert result.exit_code == 0
    assert "已加载" in result.output


def test_session_delete(runner, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    runner.invoke(cli, ["session", "save", "s1"])
    result = runner.invoke(cli, ["session", "delete", "s1"])
    assert result.exit_code == 0
    assert "已删除" in result.output
