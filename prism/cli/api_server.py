"""
PRISM Agent - CLI: api_server 命令
启动 OpenAI-compatible HTTP 服务
"""

from __future__ import annotations

import click

from prism.config import config as prism_config
from prism.config import ConfigError
from prism.api_server import PRISMApiServer


@click.group()
def api_server():
    """API Server：OpenAI-compatible HTTP 服务"""
    pass


@api_server.command()
@click.option('--host', default='127.0.0.1', show_default=True, help='监听地址')
@click.option('--port', default=8000, show_default=True, help='监听端口')
@click.option('--no-background', is_flag=True, help='前台运行，不后台启动')
def start(host: str, port: int, no_background: bool):
    """启动 API 服务"""
    try:
        prism_config.validate()
    except ConfigError as e:
        click.echo(f"[red]配置错误：{e}[/red]")
        return
    server = PRISMApiServer(host=host, port=port)
    click.echo(f"PRISM API Server 启动中: {server.url}/v1")
    if no_background:
        server.start(background=False)
    else:
        t = server.start(background=True)
        click.echo("后台运行中，按 Ctrl+C 退出")


__all__ = ['api_server']
