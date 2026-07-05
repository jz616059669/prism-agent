"""
PRISM Agent - MCP CLI commands
"""
from __future__ import annotations

import click

from prism.config import get_config
from prism.mcp import mcp_client, MCPServer
from prism.mcp.config_loader import load_mcp_config, create_default_mcp_config, setup_mcp_servers
from prism.mcp_server import mcp_server


@click.group()
def mcp():
    """MCP 客户端/服务端管理"""
    pass


@mcp.command("list")
def list_tools():
    """列出 PRISM 作为 MCP Server 暴露的全部工具"""
    tools = mcp_server.list_tools()
    for t in tools:
        name = t.get("name") if isinstance(t, dict) else getattr(t, "name", "?")
        desc = t.get("description") if isinstance(t, dict) else getattr(t, "description", "")
        click.echo(f"- {name}: {desc}")


@mcp.command("call")
@click.argument("name")
@click.argument("arguments", required=False, default="{}")
def call_tool(name: str, arguments: str):
    """调用 PRISM MCP 工具，ARGUMENTS 为 JSON 字符串"""
    try:
        import json
        args = json.loads(arguments)
    except Exception as exc:
        click.echo(f"arguments JSON 解析失败: {exc}")
        raise click.exceptions.Exit(1)
    result = mcp_server.call_tool(name, args)
    click.echo(result)


@mcp.command("init")
@click.option("--path", default=None, help="配置文件路径，默认 ~/.prism/mcp.json")
def init_config(path):
    """创建默认 MCP 服务器配置"""
    create_default_mcp_config(path)


@mcp.command("connect")
@click.option("--path", default=None, help="MCP 配置路径")
def connect_servers(path):
    """按配置连接已启用的 MCP 服务器"""
    client = setup_mcp_servers(path)
    for name in client.servers:
        click.echo(f"已连接: {name}")


@mcp.command("servers")
def list_servers():
    """列出当前 MCP 客户端已注册服务器"""
    for name, server in mcp_client.servers.items():
        click.echo(f"- {name}: {server.transport} enabled={server.enabled}")


@mcp.command("status")
def status():
    """MCP 服务端/客户端状态总览"""
    click.echo("PRISM MCP status")
    click.echo(f"- server tools: {len(mcp_server.list_tools())}")
    click.echo(f"- client servers: {len(mcp_client.servers)}")
    click.echo(f"- http available: {bool(getattr(mcp_client, 'http_clients', {}))}")
