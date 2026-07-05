"""
PRISM Agent - Memory commands
一键开关语义检索。
"""
from __future__ import annotations

import click

from prism.config import get_config
from prism.memory import persistent_memory


@click.group()
def memory():
    """记忆管理命令"""
    pass


@memory.command()
def enable_embeddings():
    """启用语义检索（使用当前 model 配置生成 embedding）"""
    model = get_config().get('model.default', '')
    provider = get_config().get('model.provider', '')
    base_url = get_config().get('model.base_url', '')
    api_key = get_config().get('model.api_key', '') or get_config()._resolve_sensitive('model.api_key', '')

    if not all([model, provider, base_url, api_key]):
        click.echo('错误：请先配置 model.default / model.provider / model.base_url / model.api_key')
        return

    # 优先使用 embedding model，如未配置则回退到 chat model
    embedding_model = get_config().get('model.embedding_model', '') or model
    try:
        persistent_memory.configure_embeddings(
            base_url=base_url,
            api_key=api_key,
            model=embedding_model,
        )
        click.echo(f'✓ 语义检索已启用，embedding model={embedding_model}')
    except Exception as exc:
        click.echo(f'启用失败：{exc}')


@memory.command()
def disable_embeddings():
    """关闭语义检索，回退到纯字符串匹配"""
    try:
        persistent_memory.configure_embeddings(base_url='', api_key='', model='')
        click.echo('✓ 语义检索已关闭')
    except Exception as exc:
        click.echo(f'关闭失败：{exc}')


@memory.command()
def status():
    """显示记忆系统状态"""
    embedding_configured = bool(getattr(persistent_memory, '_embedding_index', None) and getattr(persistent_memory._embedding_index, '_client', None))
    click.echo(f'语义检索：{"已启用" if embedding_configured else "未启用"}')
