"""
PRISM Agent - CLI: plugin 插件管理命令
"""

from __future__ import annotations

import click

from prism.config import config as prism_config
from prism.config import ConfigError
from prism.plugins import plugin_manager


@click.group()
def plugin():
    """插件管理"""
    pass


@plugin.command()
@click.argument('source')
def install(source: str):
    """安装插件（本地目录路径）"""
    try:
        result = plugin_manager.install(source)
        if result.get("success"):
            click.echo(f"插件已安装: {result.get('plugin')} v{result.get('version')}")
        else:
            click.echo(f"[red]安装失败: {result.get('error')}[/red]")
    except Exception as exc:
        click.echo(f"[red]安装失败: {exc}[/red]")


@plugin.command()
@click.argument('name')
def uninstall(name: str):
    """卸载插件"""
    try:
        result = plugin_manager.uninstall(name)
        if result.get("success"):
            click.echo(f"插件已卸载: {name}")
        else:
            click.echo(f"[red]卸载失败: {result.get('error')}[/red]")
    except Exception as exc:
        click.echo(f"[red]卸载失败: {exc}[/red]")


@plugin.command()
def list():
    """列出所有插件"""
    plugins = plugin_manager.list_plugins()
    if not plugins:
        click.echo("暂无插件")
        return
    for p in plugins:
        status = "✓" if p.get("enabled") else "✗"
        loaded = "loaded" if p.get("loaded") else "unloaded"
        click.echo(f"  {status} {p['name']} v{p['version']} [{loaded}] - {p.get('description', '')}")


@plugin.command()
@click.argument('name')
def enable(name: str):
    """启用插件"""
    result = plugin_manager.enable(name)
    if result.get("success"):
        click.echo(f"插件已启用: {name}")
    else:
        click.echo(f"[red]启用失败: {result.get('error')}[/red]")


@plugin.command()
@click.argument('name')
def disable(name: str):
    """禁用插件"""
    result = plugin_manager.disable(name)
    if result.get("success"):
        click.echo(f"插件已禁用: {name}")
    else:
        click.echo(f"[red]禁用失败: {result.get('error')}[/red]")


__all__ = ['plugin']
