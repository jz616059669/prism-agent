"""PRISM Agent - Workspace Commands"""
from __future__ import annotations

import click

from prism.logging import logger
import traceback


@click.group()
def workspace():
    """工作区命令"""
    pass


@workspace.command()
@click.argument('name')
@click.option('--path', required=True, help='工作区路径')
@click.option('--description', default='', help='工作区描述')
@click.option('--tags', multiple=True, help='工作区标签')
def create(name: str, path: str, description: str, tags: tuple):
    """创建新工作区"""
    from prism.workspace import workspace_manager
    workspace_manager.create(name, path, description, list(tags))
    click.echo(f"工作区已创建: {name}")


@workspace.command()
def list():
    """列出所有工作区"""
    from prism.workspace import workspace_manager
    workspaces = workspace_manager.list_workspaces()
    if workspaces:
        for ws in workspaces:
            click.echo(f"  - {ws['name']}: {ws['path']}")
    else:
        click.echo("暂无工作区")


@workspace.command()
@click.argument('name')
def switch(name: str):
    """切换当前工作区"""
    from prism.workspace import workspace_manager
    workspace_manager.switch(name)
    click.echo(f"已切换到工作区: {name}")


@click.command()
@click.argument('query')
def session_search(query: str):
    """搜索会话"""
    from prism.agent import create_agent
    agent = create_agent()
    results = agent.search_sessions(query)
    if results:
        for r in results:
            click.echo(f"  - {r}")
    else:
        click.echo("未找到匹配会话")


@click.group()
def acp():
    """ACP 协议命令"""
    pass


@acp.command()
@click.option('--command', '-c', required=True, help='ACP agent 命令，如 codex --acp --stdio')
@click.option('--arg', multiple=True, help='额外参数')
def start(command: str, arg: tuple):
    """启动 ACP agent"""
    try:
        import subprocess
        cmd = [command] + list(arg)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        click.echo(f"ACP agent 已启动: {command}")
        click.echo("使用 Ctrl+C 停止")
        try:
            while True:
                line = input("> ")
                if line.lower() in ('exit', 'quit'):
                    break
                proc.stdin.write((line + "\n").encode())
                proc.stdin.flush()
        except KeyboardInterrupt:
            pass
        finally:
            proc.terminate()
    except Exception as e:
        click.echo(f"启动失败: {e}")


@click.command()
@click.argument('payload')
def send(payload: str):
    """发送 ACP payload"""
    try:
        import json
        data = json.loads(payload)
        click.echo(f"发送: {data}")
    except Exception as e:
        click.echo(f"发送失败: {e}")
