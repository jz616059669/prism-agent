"""
PRISM Agent - RAG 本地知识库 CLI
"""
from __future__ import annotations

import click

from prism.rag import LocalRAG
from prism.config import config as prism_config
from pathlib import Path


@click.group()
def rag():
    """本地知识库"""
    pass


@rag.command()
@click.option("--root", default=None, help="文档根目录，默认 ~/保安铁锤")
def build(root):
    """重建知识库索引"""
    root = root or prism_config.get("rag.root") or str(Path.home() / "保安铁锤")
    rag = LocalRAG(root=root)
    res = rag.build()
    click.echo(f"索引完成：{res.get('files', 0)} 个文件，{res.get('chunks', 0)} 个片段")


@rag.command()
@click.option("--root", default=None, help="文档根目录")
def refresh(root):
    """刷新索引"""
    root = root or prism_config.get("rag.root") or str(Path.home() / "保安铁锤")
    rag = LocalRAG(root=root)
    res = rag.refresh()
    click.echo(f"已刷新：{res.get('files', 0)} 个文件，{res.get('chunks', 0)} 个片段")


@rag.command()
def stats():
    """查看索引状态"""
    root = prism_config.get("rag.root") or str(Path.home() / "保安铁锤")
    rag = LocalRAG(root=root)
    s = rag.stats()
    click.echo(f"目录：{s.get('root')}")
    click.echo(f"文件：{s.get('files')}")
    click.echo(f"片段：{s.get('chunks')}")


@rag.command()
@click.argument("query")
@click.option("--top-k", default=3, help="返回条数")
def query(query, top_k):
    """语义检索"""
    root = prism_config.get("rag.root") or str(Path.home() / "保安铁锤")
    rag = LocalRAG(root=root)
    hits = rag.query(query, top_k=top_k)
    for i, h in enumerate(hits, 1):
        click.echo(f"[{i}] {h.get('path')} | score={h.get('score')}")
        click.echo((h.get('text') or '').strip()[:500])
        click.echo("---")
