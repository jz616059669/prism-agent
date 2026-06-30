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
import logging
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.prompt import Prompt

from prism.config import config as prism_config
from prism.config import ConfigError
from prism.agent import create_agent

console = Console()

# 统一日志配置
LOG_DIR = Path.home() / ".prism" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "prism.log"

logger = logging.getLogger("prism")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# 文件日志，带轮转
from logging.handlers import RotatingFileHandler
fh = RotatingFileHandler(LOG_FILE, encoding="utf-8", maxBytes=5 * 1024 * 1024, backupCount=5)
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

# 控制台日志只显示 WARNING+
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
ch.setFormatter(formatter)
logger.addHandler(ch)


@click.group()
@click.version_option(version="1.0.1", prog_name="PRISM")
def cli():
    """
    PRISM Agent - 统一 AI Agent CLI
    
    整合 Hermes/Codex/OpenClaw 优势的新一代 AI Agent
    """
    # 配置校验延后到实际需要时执行，避免影响 help / version 等命令



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
        from prism.providers.manager import provider_pool
        providers = provider_pool.list_providers()
        table.add_row("Providers", "[green]✓[/green]", f"{len(providers)} available")
    except Exception as e:
        table.add_row("Providers", "[red]✗[/red]", str(e))

    # Check tools
    try:
        from prism.tools.registry import registry
        tools = registry.list_tools()
        table.add_row("Tools", "[green]✓[/green]", f"{len(tools)} registered")
    except Exception as e:
        table.add_row("Tools", "[red]✗[/red]", str(e))

    # Check hooks
    try:
        hooks = hook_manager.get_hooks("*")
        table.add_row("Hooks", "[green]✓[/green]", f"{len(hooks)} active")
    except Exception as e:
        table.add_row("Hooks", "[red]✗[/red]", str(e))

    # Check workspaces
    try:
        workspaces = workspace_manager.list_workspaces()
        table.add_row("Workspaces", "[green]✓[/green]", f"{len(workspaces)} configured")
    except Exception as e:
        table.add_row("Workspaces", "[red]✗[/red]", str(e))

    # Check sessions
    try:
        from prism.agent import Agent
        sessions = Agent.list_sessions()
        table.add_row("Sessions", "[green]✓[/green]", f"{len(sessions)} saved")
    except Exception as e:
        table.add_row("Sessions", "[red]✗[/red]", str(e))

    console.print(table)


@cli.command()
@click.argument('prompt')
@click.option('--stream/--no-stream', default=True, help='Stream response')
@click.option('--model', default=None, help='Override model')
@click.option('--json', 'output_json', is_flag=True, help='Output as JSON')
def ask(prompt: str, stream: bool, model: Optional[str], output_json: bool):
    """非交互模式：直接提问并输出结果（适合脚本/管道）"""
    from prism.agent import create_agent
    from prism.providers.manager import provider_pool
    
    agent = create_agent()
    
    if model:
        provider_pool.set_default_model(model)
    
    if output_json:
        result = agent.chat(prompt)
        import json
        click.echo(json.dumps({"content": result}, ensure_ascii=False))
    elif stream:
        full_response = []
        def on_chunk(chunk):
            full_response.append(chunk)
            click.echo(chunk, nl=False)
        agent.chat(prompt, on_stream=on_chunk)
        click.echo()
    else:
        result = agent.chat(prompt)
        click.echo(result)

@cli.group()
def acp():
    """ACP 协议通信命令"""
    pass


@acp.command()
@click.option('--command', '-c', required=True, help='ACP agent 命令，如 codex --acp --stdio')
@click.option('--arg', multiple=True, help='额外参数')
def start(command: str, arg: tuple):
    """启动 ACP 客户端"""
    from prism.acp.client import ACPClient
    client = ACPClient(command, list(arg))
    result = client.start()
    if result.get('success'):
        console.print("[green]✓[/green] ACP client 已启动")
    else:
        console.print(f"[red]✗[/red] 启动失败: {result.get('error')}")


@acp.command()
@click.argument('payload')
def send(payload: str):
    """向 ACP agent 发送 JSON-RPC payload"""
    from prism.acp.client import ACPClient
    import json
    client = ACPClient("echo")
    client.start()
    try:
        data = json.loads(payload)
    except Exception as e:
        console.print(f"[red]✗[/red] JSON 解析失败: {e}")
        return
    result = client.send(data)
    if result.get('success'):
        console.print_json(data=result.get('result'))
    else:
        console.print(f"[red]✗[/red] 发送失败: {result.get('error')}")


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
@click.option('--webhook', is_flag=True, help='启用本地 Webhook 接收（仅飞书）')
@click.option('--host', default='127.0.0.1', help='Webhook 监听地址')
@click.option('--port', default=9000, type=int, help='Webhook 监听端口')
def start(platform: Optional[str], token: Optional[str], app_id: Optional[str], 
          app_secret: Optional[str], encrypt_key: Optional[str], verification_token: Optional[str],
          webhook: bool, host: str, port: int):
    """启动 Gateway 服务"""
    from prism.gateway import gateway as gw
    
    # 若未指定平台，显示已配置平台
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
    cfg['gateway']['platforms'] = list(set((cfg['gateway'].get('platforms') or []) + [platform]))
    
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)
    
    click.echo(f"Gateway 配置已保存到 {config_path}")
    click.echo(f"平台: {platform}")
    
    # 真实启动适配器
    started = False
    if platform == 'feishu':
        try:
            from prism.gateway.feishu import FeishuAdapter, FeishuConfig
            adapter = FeishuAdapter(FeishuConfig(
                app_id=app_id or '',
                app_secret=app_secret or '',
                encrypt_key=encrypt_key,
                verification_token=verification_token,
            ))
            gw.register('feishu', adapter)
            gw.start(lambda m: click.echo(f"[feishu] {m.message.get('text','')}"))
            started = True
            click.echo("feishu WebSocket 已启动")
        except Exception as e:
            click.echo(f"feishu 启动失败: {e}")
    elif platform == 'telegram':
        try:
            from prism.gateway.telegram import TelegramAdapter, TelegramConfig
            adapter = TelegramAdapter(TelegramConfig(bot_token=token or ''))
            gw.register('telegram', adapter)
            if webhook:
                adapter.start_webhook(lambda m: click.echo(f"[telegram] {m.text}"), host=host, port=port)
                started = True
                click.echo("telegram webhook 已启动")
            else:
                gw.start(lambda m: click.echo(f"[telegram] {m.text}"))
                started = True
                click.echo("telegram 已启动")
        except Exception as e:
            click.echo(f"telegram 启动失败: {e}")
    elif platform == 'wechat':
        try:
            from prism.gateway.wechat import WechatAdapter, WechatConfig
            adapter = WechatAdapter(WechatConfig(
                corp_id=app_id or '',
                agent_id=app_secret or '',
                secret=token or '',
                token=token,
            ))
            gw.register('wechat', adapter)
            gw.start(lambda m: click.echo(f"[wechat] {m.text}"))
            started = True
            click.echo("wechat 已启动")
        except Exception as e:
            click.echo(f"wechat 启动失败: {e}")
    
    if not started:
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
        elif platform == 'wechat':
            click.echo("\n企业微信 Gateway 启动说明：")
            click.echo("1. 创建企业微信应用")
            click.echo("2. 获取 corp_id / agent_id / secret")
            click.echo("3. 使用 prism gateway start --platform wechat --app-id <CORP_ID> --app-secret <AGENT_ID> --token <SECRET> 启动")


@gateway.command()
@click.argument('platform')
def stop(platform: str):
    """停止 Gateway 服务"""
    from prism.gateway import gateway as gw
    adapter = gw.get_adapter(platform)
    if adapter is None:
        click.echo(f"未找到平台: {platform}")
        return
    try:
        if hasattr(adapter, 'stop'):
            adapter.stop()
        gw.unregister(platform)
        click.echo(f"{platform} Gateway 已停止")
    except Exception as e:
        click.echo(f"停止失败: {e}")


@gateway.command()
def status():
    """查看 Gateway 状态"""
    from prism.gateway import gateway as gw
    platforms = gw.list_platforms()
    if platforms:
        for name in platforms:
            adapter = gw.get_adapter(name)
            running = getattr(adapter, 'running', False)
            status_text = "运行中" if running else "已停止"
            click.echo(f"{name}: {status_text}")
    else:
        click.echo("未运行任何 Gateway")


@cli.group()
def session():
    """会话持久化命令"""
    pass


@session.command()
def list():
    """列出已保存的会话"""
    from prism.agent import create_agent
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
    agent = create_agent()
    path = agent.save_session(name)
    console.print(f"[green]✓[/green] 已保存：{path}")


@session.command()
@click.argument('name')
def load(name: str):
    """加载会话"""
    from prism.agent import create_agent
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
    agent = create_agent()
    ok = agent.delete_session(name)
    if ok:
        console.print(f"[green]✓[/green] 已删除：{name}")
    else:
        console.print(f"[red]✗[/red] 删除失败：{name}")


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
@click.argument('query')
def search(query: str):
    """搜索 Skills（优先远程 Hub，回退本地匹配）"""
    from prism.skills import skills
    console = Console()
    console.print(f"\n[bold cyan]搜索 Skills：[/bold cyan] {query}\n")
    matched = []
    try:
        matched = skills.search_hub(query)
    except Exception:
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
    console = Console()
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
        all_config = prism_config.show()
        console.print_json(data=all_config)


@cli.command()
@click.option('--model', '-m', help='模型名称')
@click.option('--provider', '-p', help='提供商')
def chat(model: Optional[str], provider: Optional[str]):
    
    # 启动前校验配置
    try:
        prism_config.validate()
    except ConfigError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        return
    console.print(Panel.fit(
        "[bold cyan]PRISM Agent[/bold cyan] [dim]v1.0.1[/dim]\n"
        "整合 Hermes + Codex + OpenClaw 能力\n"
        "输入 /help 查看命令，/exit 退出",
        border_style="cyan"
    ))
    
    # 创建 Agent
    agent = create_agent()
    
    # 显示当前模型
    current_model = model or prism_config.get('model.default', 'gpt-4o')
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
    try:
        prism_config.validate()
    except ConfigError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        return
    agent = create_agent()
    response = agent.chat(message)
    console.print(Markdown(response))


@cli.command()
def tools():
    """列出所有可用工具"""
    try:
        prism_config.validate()
    except ConfigError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        return
    agent = create_agent()
    show_tools(agent)


@cli.command()
def model():
    """显示当前模型配置"""
    try:
        prism_config.validate()
    except ConfigError as e:
        console.print(f"[red]配置错误：{e}[/red]")
        return
    show_model()


@cli.command()
def version():
    """显示版本信息"""
    console.print("PRISM Agent v1.0.1")
    console.print("整合 Hermes + Codex + OpenClaw 能力")


@cli.command()
def doctor():
    """运行健康检查：配置、模型、浏览器、日志"""
    from pathlib import Path
    checks = []

    # 1. 配置校验
    try:
        prism_config.validate()
        checks.append(("配置", True, "model.default={}, provider={}".format(
            prism_config.get("model.default"), prism_config.get("model.provider")
        )))
    except ConfigError as e:
        checks.append(("配置", False, str(e)))

    # 2. 提供商可用性
    providers = []
    try:
        providers = provider_pool.list_providers()
    except Exception as e:
        pass
    if providers:
        checks.append(("提供商", True, ", ".join(providers)))
    else:
        checks.append(("提供商", False, "未配置可用提供商"))

    # 3. 浏览器
    try:
        from prism.tools.browser import browser as browser_api
        browser_ok = bool(browser_api)
        checks.append(("浏览器", browser_ok, "已加载" if browser_ok else "模块不可用"))
    except Exception as e:
        checks.append(("浏览器", False, str(e)))

    # 5. Gateway 平台
    try:
        from prism.gateway import gateway as gw
        platforms = gw.list_platforms()
        if platforms:
            checks.append(("Gateway", True, f"平台: {', '.join(platforms)}"))
        else:
            checks.append(("Gateway", False, "未运行任何 Gateway"))
    except Exception as e:
        checks.append(("Gateway", False, str(e)))

    # 6. Skills
    try:
        from prism.skills import skills as skill_registry
        skill_list = skill_registry.list_skills()
        checks.append(("Skills", True, f"已安装 {len(skill_list)} 个"))
    except Exception as e:
        checks.append(("Skills", False, str(e)))

    # 7. MCP
    try:
        mcp_servers = prism_config.get("mcp.servers") or []
        checks.append(("MCP", True, f"已配置 {len(mcp_servers)} 个服务器"))
    except Exception as e:
        checks.append(("MCP", False, str(e)))

    # 输出
    console.print("\n[bold cyan]PRISM Doctor[/bold cyan]\n")
    for name, ok, detail in checks:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        console.print(f"  {status} {name}: {detail}")
    console.print()


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
    model = prism_config.get('model.default', 'gpt-4o')
    provider = prism_config.get('model.provider', 'openai')
    base_url = prism_config.get('model.base_url', '')
    
    console.print(f"\n[bold cyan]当前模型配置：[/bold cyan]")
    console.print(f"  模型: [green]{model}[/green]")
    console.print(f"  提供商: [green]{provider}[/green]")
    console.print(f"  API地址: [green]{base_url}[/green]\n")


def main():
    """主入口"""
    cli()


if __name__ == '__main__':
    main()
