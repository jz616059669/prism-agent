"""PRISM Agent - Quick Setup Commands"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import click
import yaml

from prism.logging import logger


def _resolve_config_path() -> Path:
    return Path(os.environ.get("PRISM_HOME", Path.home() / ".prism")) / "config.yaml"


def _load_config(path: Path) -> dict:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    return {}


def _save_config(path: Path, cfg: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, default_flow_style=False)


@click.group()
def setup():
    """快速配置向导"""
    pass


@setup.command()
@click.option('--app-id', required=True, help='飞书 App ID')
@click.option('--app-secret', required=True, help='飞书 App Secret')
@click.option('--encrypt-key', default='', help='飞书 Encrypt Key（可选）')
@click.option('--verification-token', default='', help='飞书 Verification Token（可选）')
@click.option('--start', is_flag=True, default=True, help='配置后自动启动 Gateway')
def feishu(app_id: str, app_secret: str, encrypt_key: str, verification_token: str, start: bool):
    """一键配置飞书并启动
    
    示例:
      prism setup feishu --app-id cli_xxxx --app-secret xxxx
    """
    config_path = _resolve_config_path()
    cfg = _load_config(config_path)

    if "gateway" not in cfg:
        cfg["gateway"] = {}
    cfg["gateway"]["feishu"] = {
        "token": "",
        "app_id": app_id or "",
        "app_secret": app_secret or "",
        "encrypt_key": encrypt_key or "",
        "verification_token": verification_token or "",
    }
    cfg["gateway"]["platforms"] = list(
        set((cfg["gateway"].get("platforms") or []) + ["feishu"])
    )

    _save_config(config_path, cfg)
    click.echo(click.style(f"✅ 飞书配置已写入: {config_path}", fg="green"))
    click.echo(f"   app_id: {app_id}")
    click.echo(f"   app_secret: {'*' * len(app_secret)}")
    click.echo(f"   encrypt_key: {'*' * len(encrypt_key) if encrypt_key else '(空)'}")
    click.echo(f"   verification_token: {'*' * len(verification_token) if verification_token else '(空)'}")

    if start:
        click.echo("\n正在启动飞书 Gateway ...")
        try:
            from prism.gateway import gateway as gw
            from prism.gateway.feishu import FeishuAdapter, FeishuConfig
            adapter = FeishuAdapter(FeishuConfig(
                app_id=app_id,
                app_secret=app_secret,
                encrypt_key=encrypt_key,
                verification_token=verification_token,
            ))
            gw.register("feishu", adapter)
            gw.start(lambda m: click.echo(f"[feishu] {m.message.get('text','')}"))
            click.echo(click.style("✅ 飞书 WebSocket Gateway 已启动", fg="green"))
            click.echo("\n你现在可以在飞书上直接给机器人发消息了。")
        except Exception as e:
            click.echo(click.style(f"❌ 启动失败: {e}", fg="red"))
            click.echo("\n请检查:")
            click.echo("1. 飞书应用已开启机器人能力")
            click.echo("2. App ID / App Secret 正确")
            click.echo("3. 网络可访问 open.feishu.cn")
            import traceback
            logger.debug("feishu setup start failed: %s", traceback.format_exc())
    else:
        click.echo("\n配置完成，稍后运行: prism gateway start --platform feishu")


@setup.command()
@click.option('--token', required=True, help='Telegram Bot Token')
@click.option('--start', is_flag=True, default=True, help='配置后自动启动')
def telegram(token: str, start: bool):
    """一键配置 Telegram 并启动"""
    config_path = _resolve_config_path()
    cfg = _load_config(config_path)

    if "gateway" not in cfg:
        cfg["gateway"] = {}
    cfg["gateway"]["telegram"] = {
        "token": token,
        "app_id": "",
        "app_secret": "",
        "encrypt_key": "",
        "verification_token": "",
    }
    cfg["gateway"]["platforms"] = list(
        set((cfg["gateway"].get("platforms") or []) + ["telegram"])
    )

    _save_config(config_path, cfg)
    click.echo(click.style(f"✅ Telegram 配置已写入: {config_path}", fg="green"))

    if start:
        try:
            from prism.gateway import gateway as gw
            from prism.gateway.telegram import TelegramAdapter, TelegramConfig
            adapter = TelegramAdapter(TelegramConfig(bot_token=token))
            gw.register("telegram", adapter)
            gw.start(lambda m: click.echo(f"[telegram] {m.text}"))
            click.echo(click.style("✅ Telegram Gateway 已启动", fg="green"))
        except Exception as e:
            click.echo(click.style(f"❌ 启动失败: {e}", fg="red"))


@setup.command()
@click.option('--corp-id', required=True, help='企业微信 Corp ID')
@click.option('--agent-id', required=True, help='企业微信 Agent ID')
@click.option('--secret', required=True, help='企业微信 Secret')
@click.option('--token', required=False, help='Token（可选）')
@click.option('--start', is_flag=True, default=True, help='配置后自动启动')
def wechat(corp_id: str, agent_id: str, secret: str, token: Optional[str], start: bool):
    """一键配置企业微信并启动"""
    config_path = _resolve_config_path()
    cfg = _load_config(config_path)

    if "gateway" not in cfg:
        cfg["gateway"] = {}
    cfg["gateway"]["wechat"] = {
        "token": token or secret,
        "app_id": corp_id,
        "app_secret": agent_id,
        "encrypt_key": "",
        "verification_token": "",
    }
    cfg["gateway"]["platforms"] = list(
        set((cfg["gateway"].get("platforms") or []) + ["wechat"])
    )

    _save_config(config_path, cfg)
    click.echo(click.style(f"✅ 企业微信配置已写入: {config_path}", fg="green"))

    if start:
        try:
            from prism.gateway import gateway as gw
            from prism.gateway.wechat import WechatAdapter, WechatConfig
            adapter = WechatAdapter(WechatConfig(
                corp_id=corp_id,
                agent_id=agent_id,
                secret=secret,
                token=token or secret,
            ))
            gw.register("wechat", adapter)
            gw.start(lambda m: click.echo(f"[wechat] {m.text}"))
            click.echo(click.style("✅ 企业微信 Gateway 已启动", fg="green"))
        except Exception as e:
            click.echo(click.style(f"❌ 启动失败: {e}", fg="red"))


def register_setup(cli: Any) -> None:
    """注册 setup 命令组到主 CLI"""
    try:
        cli.add_command(setup, name="setup")
    except Exception as exc:
        logger.debug("register setup command failed: %s", exc)
