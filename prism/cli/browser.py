"""PRISM Agent - Browser Commands"""
from __future__ import annotations

import click

from rich.console import Console

console = Console()


@click.group()
def browser():
    """浏览器控制命令"""
    pass


@browser.command()
@click.argument('url')
@click.option('--headless/--no-headless', default=True, help='无头模式')
def open(url: str, headless: bool):
    """打开网页"""
    from prism.tools.browser import browser as browser_api
    result = browser_api.navigate(url, headless=headless)
    if result.get('success'):
        console.print(f"[green]✓[/green] 已打开: {url}")
        console.print(f"标题: {result.get('title', 'N/A')}")
        console.print(f"状态码: {result.get('status', 'N/A')}")
    else:
        console.print(f"[red]✗[/red] 打开失败: {result.get('error')}")


@browser.command()
def close():
    """关闭浏览器"""
    from prism.tools.browser import browser as browser_api
    result = browser_api.disconnect()
    if result.get('success'):
        console.print(f"[green]✓[/green] {result.get('message')}")
    else:
        console.print(f"[red]✗[/red] {result.get('error')}")
