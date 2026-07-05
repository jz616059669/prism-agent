"""Tests for MCP config validation and cache metrics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.mcp.config_loader import validate_mcp_config, MCPConfigError
from prism.mcp import mcp_client


def test_validate_bad_transport():
    data = {"bad": {"transport": "ftp", "command": "npx"}}
    result = validate_mcp_config(data)
    assert "bad" in result
    assert any("transport" in e for e in result["bad"])


def test_validate_stdio_missing_command():
    data = {"fs": {"transport": "stdio", "url": "http://x"}}
    result = validate_mcp_config(data)
    assert "fs" in result
    assert any("command" in e for e in result["fs"])


def test_validate_http_missing_url():
    data = {"svc": {"transport": "http", "command": "python"}}
    result = validate_mcp_config(data)
    assert "svc" in result
    assert any("url" in e for e in result["svc"])


def test_cache_metrics():
    metrics = mcp_client.get_cache_metrics()
    assert "hits" in metrics
    assert "misses" in metrics
    assert metrics["size"] == 0
    mcp_client.set_cache_ttl(120)
    assert mcp_client._cache_ttl == 120
