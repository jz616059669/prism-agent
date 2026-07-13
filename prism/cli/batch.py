"""
PRISM Agent - CLI: batch 批量处理命令
用法：
  prism batch run --input prompts.json --output results.json --sharegpt
  prism batch summary --input results.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import click

from prism.logging import logger
from prism.config import config as prism_config
from prism.config import ConfigError
from prism.batch import BatchProcessor, BatchItem, BatchResult


@click.group()
def batch():
    """批量处理 prompts"""
    pass


@batch.command()
@click.option('--input', 'input_path', required=True, help='JSON 文件路径，数组格式 [{"prompt":"..."}, ...]')
@click.option('--output', 'output_path', default='batch-results.json', help='结果 JSON 文件路径')
@click.option('--sharegpt', 'sharegpt_path', default=None, help='同时导出 ShareGPT 格式文件')
@click.option('--workers', default=4, show_default=True, help='并发 worker 数')
@click.option('--retry', default=1, show_default=True, help='失败重试次数')
def run(input_path: str, output_path: str, sharegpt_path: Optional[str], workers: int, retry: int):
    """批量执行 prompts"""
    try:
        prism_config.validate()
    except ConfigError as e:
        click.echo(f"[red]配置错误：{e}[/red]")
        return
    from prism.agent import create_agent
    try:
        data = json.loads(Path(input_path).read_text(encoding='utf-8'))
    except Exception as exc:
        click.echo(f"[red]读取输入文件失败: {exc}[/red]")
        return
    if not isinstance(data, list):
        click.echo("[red]输入文件应为 JSON 数组[/red]")
        return
    items = [BatchItem(prompt=str(x.get('prompt', x) if isinstance(x, dict) else x), meta=x if isinstance(x, dict) else {}) for x in data]
    click.echo(f"开始批量处理，共 {len(items)} 条，workers={workers}，retry={retry}")
    processor = BatchProcessor(agent_factory=lambda sid: create_agent(), max_workers=workers, retry=retry)
    results = processor.run(items)
    payload = [
        {
            'index': r.index,
            'success': r.success,
            'prompt': r.prompt,
            'content': r.content,
            'error': r.error,
            'model': r.model,
            'meta': r.meta,
        }
        for r in results
    ]
    Path(output_path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    click.echo(f"结果已写入: {output_path}")
    if sharegpt_path:
        sg = processor.to_sharegpt(results)
        Path(sharegpt_path).write_text(json.dumps(sg, ensure_ascii=False, indent=2), encoding='utf-8')
        click.echo(f"ShareGPT 已导出: {sharegpt_path}")
    summary = processor.summary(results)
    click.echo(f"完成: total={summary['total']}, success={summary['success']}, failed={summary['failed']}")


@batch.command()
@click.option('--input', 'input_path', required=True, help='结果 JSON 文件路径')
def summary(input_path: str):
    """查看批量结果摘要"""
    try:
        data = json.loads(Path(input_path).read_text(encoding='utf-8'))
    except Exception as exc:
        click.echo(f"[red]读取失败: {exc}[/red]")
        return
    if not isinstance(data, list):
        click.echo("[red]输入文件应为 JSON 数组[/red]")
        return
    total = len(data)
    ok = sum(1 for x in data if x.get('success'))
    failed = total - ok
    click.echo(f"total={total}, success={ok}, failed={failed}, success_rate={round(ok/total,4) if total else 0}")


__all__ = ['batch']
