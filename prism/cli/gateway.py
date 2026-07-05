"""PRISM Agent - Gateway Commands"""
from __future__ import annotations

from typing import Optional

import click

from prism.logging import logger
import traceback


@click.group()
def gateway():
    """Gateway 控制命令"""
    click.echo("用法: prism gateway start/stop/status --help")


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
def start(
    platform: Optional[str],
    token: Optional[str],
    app_id: Optional[str],
    app_secret: Optional[str],
    encrypt_key: Optional[str],
    verification_token: Optional[str],
    webhook: bool,
    host: str,
    port: int,
):
    """启动 Gateway 服务"""
    from prism.gateway import gateway as gw
    from pathlib import Path

    if not platform:
        platforms = gw.list_platforms()
        if platforms:
            click.echo(f"已配置平台: {', '.join(platforms)}")
        else:
            click.echo("未配置任何平台，请用 --platform 指定")
        return

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

    started = False
    if platform == 'feishu':
        try:
            from prism.gateway.feishu import FeishuAdapter, FeishuConfig
            adapter = FeishuAdapter(FeishuConfig(
                app_id=app_id or '',
                app_secret=app_secret or '',
                encrypt_key=encrypt_key or '',
                verification_token=verification_token or '',
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
                token=token or '',
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


@gateway.command()
@click.option('--timeout', default=10, type=int, help='健康检查超时秒数')
def health(timeout: int):
    """检查 Gateway 各平台接入健康状态"""
    from prism.gateway import gateway as gw

    platforms = gw.list_platforms()
    if not platforms:
        click.echo("未配置任何 Gateway 平台")
        return

    results = []
    for name in platforms:
        adapter = gw.get_adapter(name)
        status = {"platform": name, "status": "unknown", "detail": ""}
        try:
            if name == "telegram" and adapter is not None:
                info = adapter.get_me()
                if info.get("success"):
                    status["status"] = "ok"
                    status["detail"] = f"bot={info.get('bot', {}).get('username', '?')}"
                else:
                    status["status"] = "error"
                    status["detail"] = info.get("error", "get_me failed")
            elif name == "discord" and adapter is not None:
                info = adapter.get_current_user()
                if info.get("success"):
                    status["status"] = "ok"
                    status["detail"] = f"user={info.get('user', {}).get('username', '?')}"
                else:
                    status["status"] = "error"
                    status["detail"] = info.get("error", "get_current_user failed")
            elif name == "feishu":
                status["status"] = "configured"
                status["detail"] = "websocket mode; use start to verify"
            elif name == "wechat":
                status["status"] = "not_implemented"
                status["detail"] = "callback service not implemented"
            else:
                status["status"] = "unknown"
                status["detail"] = "adapter missing"
        except Exception as e:
            status["status"] = "error"
            status["detail"] = str(e)
        results.append(status)

    for item in results:
        color = {"ok": "green", "configured": "cyan", "not_implemented": "yellow"}.get(item["status"], "red")
        click.echo(click.style(f"{item['platform']}: {item['status']}", fg=color), nl=False)
        if item["detail"]:
            click.echo(f" - {item['detail']}")
        else:
            click.echo("")
