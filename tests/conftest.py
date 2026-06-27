import pytest
from prism.mcp import mcp_client


@pytest.fixture(autouse=True)
def _reset_mcp_client():
    """每个测试后清理 mcp_client 全局状态，避免测试顺序依赖"""
    yield
    try:
        mcp_client.servers.clear()
        mcp_client.processes.clear()
        mcp_client.tools.clear()
        mcp_client.http_clients.clear()
        mcp_client._stdio_initialized.clear()
        mcp_client._stdio_locks.clear()
    except Exception:
        pass
