"""
PRISM Agent - ACP 协议测试
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.acp.client import ACPClient


def test_acp_client_start_failure():
    client = ACPClient("nonexistent_command_xyz")
    result = client.start()
    assert result["success"] is False
    assert "error" in result


def test_acp_client_send_without_start():
    client = ACPClient("echo")
    result = client.send({"method": "ping"})
    assert result["success"] is False
    assert "not started" in result.get("error", "").lower()
