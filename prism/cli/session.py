"""PRISM Agent - Session Commands"""
from __future__ import annotations

import click

from prism.logging import logger
import traceback


@click.group()
def session():
    """会话持久化命令"""
    click.echo("用法: prism session list/save/load/delete --help")


@session.command()
def list():
    """列出已保存的会话"""
    from prism.agent import create_agent
    from rich.console import Console
    console = Console()
    agent = create_agent()
    names = agent.list_sessions()
    if names:
        console.print("已保存会话：")
        for name in names:
            console.print(f"  - {name}")
    else:
        console.print("暂无已保存会话")


@session.command()
@click.argument('name')
def save(name: str):
    """保存当前会话"""
    from prism.agent import create_agent
    from rich.console import Console
    console = Console()
    agent = create_agent()
    path = agent.save_session(name)
    console.print(f"[green]✓[/green] 已保存：{path}")


@session.command()
@click.argument('name')
def load(name: str):
    """加载会话"""
    from prism.agent import create_agent
    from rich.console import Console
    console = Console()
    agent = create_agent()
    ok = agent.load_session(name)
    if ok:
        console.print(f"[green]✓[/green] 已加载：{name}")
    else:
        console.print(f"[red]✗[/red] 加载失败：{name}")


@session.command()
@click.argument('name')
def delete(name: str):
    """删除会话"""
    from prism.agent import create_agent
    from rich.console import Console
    console = Console()
    agent = create_agent()
    ok = agent.delete_session(name)
    if ok:
        console.print(f"[green]✓[/green] 已删除：{name}")
    else:
        console.print(f"[red]✗[/red] 删除失败：{name}")
