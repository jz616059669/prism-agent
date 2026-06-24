"""Unified smoke test for PRISM modules"""
import pytest
from prism.providers.manager import ProviderPool
from prism.providers.fallback import FallbackManager
from prism.providers.pool import CredentialPool
from prism.mcp import mcp_client, MCPServer


def test_providers_import():
    pool = ProviderPool()
    assert isinstance(pool.list_providers(), list)


def test_fallback_manager():
    fm = FallbackManager(["stepfun", "openai"])
    assert fm.fallback_chain == ["stepfun", "openai"]


def test_credential_pool():
    pool = CredentialPool("stepfun", [{"api_key": "demo"}])
    assert pool.next() == {"api_key": "demo"}


def test_mcp_add_stdio_server():
    server = MCPServer(
        name="echo",
        transport="stdio",
        command="python",
        args=["-c", "import sys, json; print(json.dumps({'jsonrpc':'2.0','id':1,'result':{'tools':[]}}))"],
        enabled=True,
    )
    mcp_client.add_server(server)
    tools = mcp_client.list_tools("echo")
    assert isinstance(tools, list)
