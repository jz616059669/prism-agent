"""PRISM Agent - Skill Commands"""
from __future__ import annotations

import click

from prism.logging import logger
import traceback
from rich.console import Console

console = Console()


@click.group()
def skill():
    """Skills 管理命令"""
    pass


@skill.command()
def list():
    """列出所有已安装的 Skills"""
    from prism.skills import skills
    skill_list = skills.list_skills()
    console.print("\n[bold cyan]已安装 Skills：[/bold cyan]")
    for s in skill_list:
        status = "[green]✓[/green]" if s.get('enabled', True) else "[red]✗[/red]"
        console.print(f"  {status} [green]{s['name']}[/green]: {s['description']}")
    console.print()


@skill.command()
@click.argument('query')
def search(query: str):
    """搜索 Skills（优先远程 Hub，回退本地匹配）"""
    from prism.skills import skills
    console.print(f"\n[bold cyan]搜索 Skills：[/bold cyan] {query}\n")
    matched = []
    try:
        matched = skills.search_hub(query)
    except Exception:
        logger.debug("search hub failed: %s", traceback.format_exc())
        matched = []
    if matched:
        console.print("[yellow]远程 Hub 结果：[/yellow]\n")
        for item in matched:
            name = item.get('name', 'unknown')
            desc = item.get('description', '')
            console.print(f"  [green]{name}[/green]: {desc}")
        console.print()
        return
    local_matches = skills.match(query)
    if local_matches:
        for s in local_matches:
            console.print(f"  [green]✓[/green] [green]{s.name}[/green]: {s.description}")
    else:
        console.print("[yellow]未找到匹配的 Skills[/yellow]\n")


@skill.command()
def browse():
    """浏览远程 Hub Skills"""
    from prism.skills import skills
    items = skills.browse_hub()
    console.print("\n[bold cyan]远程 Hub Skills：[/bold cyan]\n")
    if not items:
        console.print("[yellow]暂无可浏览的远程 Skills[/yellow]\n")
        return
    for item in items:
        name = item.get('name', 'unknown')
        desc = item.get('description', '')
        console.print(f"  [green]{name}[/green]: {desc}")
    console.print()


@skill.command()
@click.argument('name')
def install(name: str):
    """安装一个 Skill"""
    from prism.skills import skills
    result = skills.install_skill(name)
    if result.get('success'):
        console.print(f"[green]✓[/green] 已安装 skill: {name}")
    else:
        console.print(f"[red]✗[/red] 安装失败: {result.get('error', '未知错误')}")


@skill.command()
def install_builtin():
    """安装内置示例 Skills 到本地 skills 目录"""
    from pathlib import Path
    from prism.skills import skills
    builtin_dir = Path(__file__).resolve().parent.parent / 'skills' / 'builtin'
    result = skills.install_skill(str(builtin_dir))
    if result.get('success'):
        console.print(f"[green]✓[/green] {result.get('message')}")
    else:
        console.print(f"[red]✗[/red] {result.get('error', '未知错误')}")


@skill.command()
@click.argument('directory')
def install_dir(directory: str):
    """从目录批量安装 Skills"""
    from prism.skills import skills
    result = skills.install_skill(directory)
    if result.get('success'):
        console.print(f"[green]✓[/green] {result.get('message')}")
    else:
        console.print(f"[red]✗[/red] {result.get('error', '未知错误')}")


@skill.command()
@click.argument('name')
def remove(name: str):
    """移除一个 Skill"""
    from prism.skills import skills
    result = skills.uninstall_skill(name)
    if result.get('success'):
        console.print(f"[green]✓[/green] 已移除 skill: {name}")
    else:
        console.print(f"[red]✗[/red] 移除失败: {result.get('error', '未知错误')}")
