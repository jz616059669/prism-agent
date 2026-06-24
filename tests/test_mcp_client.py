"""MCP 客户端基础测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from prism.mcp import mcp_client


def test_mcp_client_initialized():
    assert mcp_client is not None
    assert hasattr(mcp_client, "servers")
    assert hasattr(mcp_client, "list_tools")
