"""PRISM Agent - Config Commands"""
from __future__ import annotations

import click

from prism.config import config as prism_config
from rich.console import Console

console = Console()


@click.group()
def config():
    """配置管理命令"""
    pass


@config.command()
@click.argument('key')
@click.argument('value')
def set(key: str, value: str):
    """设置配置项"""
    prism_config.set(key, value)
    console.print(f"[green]✓[/green] 已设置 {key} = {value}")


@config.command()
@click.argument('key', required=False)
def get(key):
    """查看配置项"""
    if key:
        value = prism_config.get(key)
        console.print(f"{key} = {value}")
    else:
        all_config = prism_config.show()
        console.print_json(data=all_config)
