"""
PRISM Agent - CLI 入口
整合 Hermes/Codex/OpenClaw 的命令行体验
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.prompt import Prompt

from prism.agent import create_agent
from prism.config import config

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="PRISM")
def cli():
    """
    PRISM Agent - 统一 AI Agent CLI
    
    整合 Hermes/Codex/OpenClaw 优势的新一代 AI Agent
    """
    pass


@cli.command()
@click.option('--model', '-m', help='模型名称')
@click.option('--provider', '-p', help='提供商')
def chat(model: Optional[str], provider: Optional[str]):
    """启动交互式聊天"""
    
    # 显示欢迎信息
    console.print(Panel.fit(
        "[bold cyan]PRISM Agent[/bold cyan] [dim]v0.1.0[/dim]\n"
        "整合 Hermes + Codex + OpenClaw 能力\n"
        "输入 /help 查看命令，/exit 退出",
        border_style="cyan"
    ))
    
    # 创建 Agent
    agent = create_agent()
    
    # 显示当前模型
    current_model = model or config.get('model.default', 'gpt-4o')
    console.print(f"[dim]当前模型: {current_model}[/dim]\n")
    
    # 对话循环
    while True:
        try:
            # 获取用户输入
            user_input = Prompt.ask("[bold green]你[/bold green]")
            
            if not user_input.strip():
                continue
            
            # 处理特殊命令
            if user_input.startswith('/'):
                cmd = user_input.lower()
                if cmd in ['/exit', '/quit']:
                    console.print("[yellow]再见！[/yellow]")
                    break
                elif cmd == '/help':
                    show_help()
                    continue
                elif cmd == '/tools':
                    show_tools(agent)
                    continue
                elif cmd == '/model':
                    show_model()
                    continue
                elif cmd == '/clear':
                    agent.clear_history()
                    console.print("[green]历史已清空[/green]")
                    continue
                else:
                    console.print(f"[red]未知命令: {cmd}[/red]")
                    continue
            
            # 发送消息给 Agent
            with console.status("[bold cyan]思考中...", spinner="dots"):
                response = agent.chat(user_input)
            
            # 显示回复
            console.print(Markdown(response))
            console.print()
            
        except KeyboardInterrupt:
            console.print("\n[yellow]再见！[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]错误: {e}[/red]")


@cli.command()
@click.argument('message')
@click.option('--model', '-m', help='模型名称')
def ask(message: str, model: Optional[str]):
    """单次提问"""
    agent = create_agent()
    response = agent.chat(message)
    console.print(Markdown(response))


@cli.command()
def tools():
    """列出所有可用工具"""
    agent = create_agent()
    show_tools(agent)


@cli.command()
def model():
    """显示当前模型配置"""
    show_model()


@cli.command()
def version():
    """显示版本信息"""
    console.print("PRISM Agent v0.1.0")
    console.print("整合 Hermes + Codex + OpenClaw 能力")


def show_help():
    """显示帮助信息"""
    help_text = """
**可用命令：**
- `/help` - 显示帮助
- `/exit` - 退出
- `/tools` - 列出所有工具
- `/model` - 显示当前模型
- `/clear` - 清空对话历史

**示例：**
- "帮我写一个Python脚本"
- "读取文件 README.md"
- "执行命令 ls -la"
- "搜索网页 Python教程"
    """
    console.print(Markdown(help_text))


def show_tools(agent):
    """显示可用工具"""
    tools = agent.list_tools()
    console.print("\n[bold cyan]可用工具：[/bold cyan]")
    for tool in tools:
        console.print(f"  • [green]{tool['name']}[/green]: {tool['description']}")
    console.print()


def show_model():
    """显示模型配置"""
    model = config.get('model.default', 'gpt-4o')
    provider = config.get('model.provider', 'openai')
    base_url = config.get('model.base_url', '')
    
    console.print(f"\n[bold cyan]当前模型配置：[/bold cyan]")
    console.print(f"  模型: [green]{model}[/green]")
    console.print(f"  提供商: [green]{provider}[/green]")
    console.print(f"  API地址: [green]{base_url}[/green]\n")


def main():
    """主入口"""
    cli()


if __name__ == '__main__':
    main()
