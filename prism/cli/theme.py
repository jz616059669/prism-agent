"""
PRISM Agent - CLI: theme 主题命令
"""

from __future__ import annotations

import click

from prism.theme import theme_manager


@click.group()
def theme():
    """主题切换"""
    pass


@theme.command()
@click.argument('name')
def set(name: str):
    """设置当前主题"""
    ok = theme_manager.set_current(name)
    if ok:
        click.echo(f"主题已切换: {name}")
    else:
        click.echo(f"[red]主题不存在: {name}[/red]")
        click.echo(f"可选主题: {', '.join(theme_manager.list_themes())}")


@theme.command()
def current():
    """显示当前主题"""
    t = theme_manager.get_current()
    click.echo(f"当前主题: {t.name}")


@theme.command()
def list():
    """列出所有主题"""
    for name in theme_manager.list_themes():
        click.echo(f"  - {name}")


__all__ = ['theme']
