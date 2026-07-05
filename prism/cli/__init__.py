"""
PRISM Agent - CLI 入口
"""
from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import click

from prism.logging import logger
import traceback
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.prompt import Prompt

from prism.config import config as prism_config
from prism.config import ConfigError
from prism.agent import create_agent
from typing import Optional

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(version="2.1.2", prog_name="PRISM")
@click.pass_context
def cli(ctx):
    """
    PRISM Agent - 统一 AI Agent CLI

    整合 Hermes/Codex/OpenClaw 优势的新一代 AI Agent
    """
    if ctx.invoked_subcommand is None:
        from rich.panel import Panel
        from prism.config import config as prism_cfg
        try:
            model = prism_cfg.get('model.default', 'unknown')
            provider = prism_cfg.get('model.provider', 'unknown')
            console.print(Panel.fit(
                f"[bold cyan]PRISM Agent[/bold cyan] [dim]v2.1.2[/dim]\n"
                f"整合 Hermes + Codex + OpenClaw 能力\n"
                f"当前模型: [green]{model}[/green] / [green]{provider}[/green]\n"
                "输入 [cyan]prism chat[/cyan] 进入交互对话，或 [cyan]prism --help[/cyan] 查看命令",
                border_style="cyan"
            ))
        except Exception:
            console.print(Panel.fit(
                "[bold cyan]PRISM Agent[/bold cyan] [dim]v2.1.2[/dim]\n"
                "整合 Hermes + Codex + OpenClaw 能力\n"
                "输入 [cyan]prism chat[/cyan] 进入交互对话，或 [cyan]prism --help[/cyan] 查看命令",
                border_style="cyan"
            ))


@cli.command()
def doctor():
    """诊断 PRISM 环境状态"""
    from rich.table import Table
    from prism.hooks import hook_manager
    from prism.workspace import workspace_manager

    table = Table(title="PRISM Doctor")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Details")

    # Check config
    try:
        from prism.config import config
        table.add_row("Config", "[green]✓[/green]", str(config.path()))
    except Exception as e:
        table.add_row("Config", "[red]✗[/red]", str(e))

    # Check provider
    try:
        from prism.models.providers import provider_pool
        providers = provider_pool.list_providers()
        table.add_row("Provider", "[green]✓[/green]", ", ".join(providers))
    except Exception:
        logger.debug("list providers failed: %s", traceback.format_exc())
        table.add_row("Provider", "[yellow]![/yellow]", "未配置")

    # Check browser
    try:
        from prism.tools.browser import browser as browser_api
        browser_ok = bool(browser_api)
        table.add_row("Browser", "[green]✓[/green]" if browser_ok else "[yellow]![/yellow]", "已加载" if browser_ok else "模块不可用")
    except Exception as e:
        table.add_row("Browser", "[red]✗[/red]", str(e))

    # Check gateway
    try:
        from prism.gateway import gateway as gw
        platforms = gw.list_platforms()
        if platforms:
            table.add_row("Gateway", "[green]✓[/green]", f"平台: {', '.join(platforms)}")
        else:
            table.add_row("Gateway", "[yellow]![/yellow]", "未运行")
    except Exception as e:
        table.add_row("Gateway", "[red]✗[/red]", str(e))

    # Check skills
    try:
        from prism.skills import skills as skill_registry
        skill_list = skill_registry.list_skills()
        table.add_row("Skills", "[green]✓[/green]", f"已安装 {len(skill_list)} 个")
    except Exception as e:
        table.add_row("Skills", "[red]✗[/red]", str(e))

    console.print(table)


@cli.command()
@click.argument('prompt')
@click.option('--stream/--no-stream', default=True, help='Stream response')
@click.option('--model', default=None, help='Override model')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def ask(prompt: str, stream: bool, model: Optional[str], output_json: bool):
    """单次提问"""
    try:
        prism_config.validate()
    except ConfigError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        return
    agent = create_agent()
    response = agent.chat(prompt)
    console.print(Markdown(response))


@cli.command()
def chat():
    """启动交互式对话"""
    try:
        prism_config.validate()
    except ConfigError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        return
    console.print(Panel.fit(
        "[bold cyan]PRISM Agent[/bold cyan] [dim]v2.1.2[/dim]\n"
        "整合 Hermes + Codex + OpenClaw 能力\n"
        "输入 /help 查看命令，/exit 退出",
        border_style="cyan"
    ))
    agent = create_agent()
    current_model = prism_config.get('model.default', 'gpt-4o')
    console.print(f"[dim]当前模型: {current_model}[/dim]\n")
    while True:
        try:
            user_input = Prompt.ask("[bold green]你[/bold green]")
            if not user_input.strip():
                continue
            if user_input.startswith('/'):
                cmd = user_input.lower()
                if cmd in ['/exit', '/quit']:
                    console.print("[yellow]再见！[/yellow]")
                    break
                elif cmd == '/help':
                    from prism.cli.commands import show_help
                    show_help()
                    continue
                elif cmd == '/tools':
                    from prism.cli.commands import show_tools
                    show_tools(agent)
                    continue
                elif cmd == '/model':
                    from prism.cli.commands import show_model
                    show_model()
                    continue
                elif cmd == '/clear':
                    agent.clear_history()
                    console.print("[green]历史已清空[/green]")
                    continue
                else:
                    console.print(f"[red]未知命令: {cmd}[/red]")
                    continue
            with console.status("[bold cyan]思考中...", spinner="dots"):
                response = agent.chat(user_input)
            console.print(Markdown(response))
            console.print()
        except KeyboardInterrupt:
            console.print("\n[yellow]再见！[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]错误: {e}[/red]")


@cli.command()
def tools():
    """列出所有可用工具"""
    try:
        prism_config.validate()
    except ConfigError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        return
    agent = create_agent()
    from prism.cli.commands import show_tools
    show_tools(agent)


@cli.command()
def model():
    """显示当前模型配置"""
    try:
        prism_config.validate()
    except ConfigError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        return
    from prism.cli.commands import show_model
    show_model()


@cli.command()
def version():
    """显示版本信息"""
    console.print("PRISM Agent v2.1.2")
    console.print("整合 Hermes + Codex + OpenClaw 能力")


# Register subcommand groups at module level so tests and imports see them
from prism.cli.gateway import gateway  # noqa: E402
from prism.cli.session import session  # noqa: E402
from prism.cli.skill import skill  # noqa: E402
from prism.cli.browser import browser  # noqa: E402
from prism.cli.config_cmds import config  # noqa: E402
from prism.cli.workspace import workspace  # noqa: E402

cli.add_command(gateway)
cli.add_command(session)
cli.add_command(skill)
cli.add_command(browser)
cli.add_command(config)
cli.add_command(workspace)


def main():
    """主入口"""
    cli()


if __name__ == '__main__':
    main()
