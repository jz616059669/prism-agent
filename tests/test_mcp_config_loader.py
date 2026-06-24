"""MCP 配置加载器集成测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import json
from prism.mcp.config_loader import load_mcp_config, setup_mcp_servers, create_default_mcp_config
from prism.mcp import mcp_client, MCPServer


def test_load_mcp_config(tmp_path):
    cfg = {
        "echo": {
            "transport": "stdio",
            "command": "python",
            "args": ["-c", "print('ok')"],
        }
    }
    cfg_file = tmp_path / "mcp.json"
    cfg_file.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    servers = load_mcp_config(str(cfg_file))
    assert len(servers) == 1
    assert servers[0].name == "echo"


def test_mcp_client_initialized():
    assert mcp_client is not None
    assert hasattr(mcp_client, "servers")
    assert hasattr(mcp_client, "list_tools")
