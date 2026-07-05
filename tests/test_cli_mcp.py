"""
PRISM Agent - MCP CLI tests
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from click.testing import CliRunner
from prism.cli.mcp import mcp


def test_mcp_list_tools():
    runner = CliRunner()
    result = runner.invoke(mcp, ["list"])
    assert result.exit_code == 0
    assert "prism_chat" in result.output


def test_mcp_call_tool_json_args():
    runner = CliRunner()
    result = runner.invoke(mcp, ["call", "prism_chat", '{"message":"hi"}'])
    assert result.exit_code == 0
    assert "result" in result.output or "content" in result.output


def test_mcp_call_tool_bad_json():
    runner = CliRunner()
    result = runner.invoke(mcp, ["call", "prism_chat", "not-json"])
    assert result.exit_code != 0
    assert "JSON" in result.output


def test_mcp_servers_empty_by_default():
    runner = CliRunner()
    result = runner.invoke(mcp, ["servers"])
    assert result.exit_code == 0
