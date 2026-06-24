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
from prism.config import config as prism_config

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="PRISM")
def cli():
    """
    PRISM Agent - 统一 AI Agent CLI
    
    整合 Hermes/Codex/OpenClaw 优势的新一代 AI Agent
    """
    pass


@cli.group()
def gateway():
    """Gateway 控制命令"""
    pass


@gateway.command()
@click.option('--platform', '-p', help='平台名称')
@click.option('--token', '-t', help='Bot Token')
@click.option('--app-id', help='飞书 App ID')
@click.option('--app-secret', help='飞书 App Secret')
@click.option('--encrypt-key', help='飞书 Encrypt Key')
@click.option('--verification-token', help='飞书 Verification Token')
def start(platform: Optional[str], token: Optional[str], app_id: Optional[str], 
          app_secret: Optional[str], encrypt_key: Optional[str], verification_token: Optional[str]):
    """启动 Gateway 服务"""
    from prism.gateway import gateway as gw
    
    if not platform:
        platforms = gw.list_platforms()
        if platforms:
            click.echo(f"已配置平台: {', '.join(platforms)}")
        else:
            click.echo("未配置任何平台，请用 --platform 指定")
        return
    
    # 保存配置到 config
    config_path = Path.home() / ".prism" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    import yaml
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f) or {}
    else:
        cfg = {}
    
    if 'gateway' not in cfg:
        cfg['gateway'] = {}
    cfg['gateway'][platform] = {
        'token': token or '',
        'app_id': app_id or '',
        'app_secret': app_secret or '',
        'encrypt_key': encrypt_key or '',
        'verification_token': verification_token or '',
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
    
    click.echo(f"Gateway 配置已保存到 {config_path}")
    click.echo(f"平台: {platform}")
    
    # 显示启动说明
    if platform == 'feishu':
        click.echo("\n飞书 Gateway 启动说明：")
        click.echo("1. 在飞书开放平台创建应用")
        click.echo("2. 开启机器人能力")
        click.echo("3. 配置事件订阅 URL")
        click.echo("4. 使用 prism gateway start --platform feishu 启动")
    elif platform == 'telegram':
        click.echo("\nTelegram Gateway 启动说明：")
        click.echo("1. 与 @BotFather 对话创建 Bot")
        click.echo("2. 获取 Bot Token")
        click.echo("3. 使用 prism gateway start --platform telegram --token <TOKEN> 启动")


@gateway.command()
@click.argument('platform')
def stop(platform: str):
    """停止 Gateway 服务"""
    click.echo(f"停止 {platform} Gateway...")
    from prism.gateway import gateway as gw
    click.echo("Gateway 已停止")


@gateway.command()
def status():
    """查看 Gateway 状态"""
    from prism.gateway import gateway as gw
    platforms = gw.list_platforms()
    if platforms:
        click.echo(f"运行中平台: {', '.join(platforms)}")
    else:
        click.echo("未运行任何 Gateway")


@cli.group()
def skill():
    """Skills 管理命令"""
    pass


@skill.command()
def list():
    """列出所有已安装的 Skills"""
    from prism.skills import skills
    skill_list = skills.list_skills()
    
    console = Console()
    console.print("\n[bold cyan]已安装 Skills：[/bold cyan]")
    for s in skill_list:
        status = "[green]✓[/green]" if s.get('enabled', True) else "[red]✗[/red]"
        console.print(f"  {status} [green]{s['name']}[/green]: {s['description']}")
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
@click.argument('name')
def remove(name: str):
    """移除一个 Skill"""
    from prism.skills import skills
    result = skills.uninstall_skill(name)
    if result.get('success'):
        console.print(f"[green]✓[/green] 已移除 skill: {name}")
    else:
        console.print(f"[red]✗[/red] 移除失败: {result.get('error', '未知错误')}")


@cli.group()
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


@cli.group()
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
def get(key: Optional[str]):
    """查看配置项"""
    if key:
        value = prism_config.get(key)
        console.print(f"{key} = {value}")
    else:
        all_config = prism_config.all()
        console.print_json(data=all_config)


@cli.command()
@click.option('--model', '-m', help='模型名称')
@click.option('--provider', '-p', help='提供商')
def chat(model: Optional[str], provider: Optional[str]):
    
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
