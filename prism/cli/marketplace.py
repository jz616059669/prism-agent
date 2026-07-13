"""
PRISM Agent - Marketplace CLI
"""
from __future__ import annotations

import json

import click

from prism.marketplace import marketplace


@click.group()
def market():
    """Agent Marketplace"""
    pass


@market.command("list")
def list_cmd():
    items = marketplace.list_packages()
    if not items:
        click.echo("暂无已发布 Agent 包")
        return
    for item in items:
        click.echo(f"[{item.get('name')}] v{item.get('version')} - {item.get('description', '')}")


@market.command("publish")
@click.argument("name")
@click.option("--version", default="1.0.0")
@click.option("--description", default="")
@click.option("--author", default="")
@click.option("--persona", default="{}")
@click.option("--skills", default="")
@click.option("--workflows", default="")
@click.option("--tags", default="")
def publish_cmd(name: str, version: str, description: str, author: str, persona: str, skills: str, workflows: str, tags: str):
    from prism.marketplace import AgentPackage
    pkg = AgentPackage(
        name=name,
        version=version,
        description=description,
        author=author,
        persona=json.loads(persona),
        skills=[s.strip() for s in skills.split(",") if s.strip()],
        workflows=[w.strip() for w in workflows.split(",") if w.strip()],
        tags=[t.strip() for t in tags.split(",") if t.strip()],
    )
    saved = marketplace.publish(pkg)
    click.echo(f"published: {saved.to_dict()}")


@market.command("install")
@click.argument("name")
def install_cmd(name: str):
    res = marketplace.install(name)
    click.echo(json.dumps(res, ensure_ascii=False))


@market.command("remove")
@click.argument("name")
def remove_cmd(name: str):
    ok = marketplace.remove(name)
    click.echo(f"removed={ok}")
