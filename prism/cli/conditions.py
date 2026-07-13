"""
PRISM Agent - Conditional Triggers CLI
"""
from __future__ import annotations

import json

import click

from prism.conditions import condition_engine


@click.group()
def conditions():
    """条件规则管理"""
    pass


@conditions.command("list")
def list_rules():
    """列出所有条件规则"""
    items = condition_engine.list_rules()
    if not items:
        click.echo("暂无规则")
        return
    for item in items:
        click.echo(f"[{item['id']}] {item.get('name', '')} enabled={item.get('enabled', False)} expr={item.get('expression', '')}")


@conditions.command("add")
@click.argument("rule_id")
@click.option("--name", default="")
@click.option("--expr", required=True)
@click.option("--enabled/--disabled", default=True)
def add_rule(rule_id: str, name: str, expr: str, enabled: bool):
    """添加条件规则"""
    rule = condition_engine.add_rule(
        condition_engine._rules.__class__(
            id=rule_id, name=name, expression=expr, enabled=enabled
        )
    )
    click.echo(f"added: {rule.to_dict()}")


@conditions.command("remove")
@click.argument("rule_id")
def remove_rule(rule_id: str):
    """删除条件规则"""
    ok = condition_engine.remove_rule(rule_id)
    click.echo(f"removed={ok}")


@conditions.command("eval")
@click.option("--expr", required=True)
@click.option("--ctx", default="{}")
def eval_rule(expr: str, ctx: str):
    """测试表达式"""
    context = json.loads(ctx)
    result = condition_engine._eval_expr(expr, context)
    click.echo(f"result={result}")
