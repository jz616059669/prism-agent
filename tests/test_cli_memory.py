"""
PRISM Agent - Memory CLI tests
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from click.testing import CliRunner


REPO_ROOT = Path(__file__).resolve().parents[1]
MEM_FILE = REPO_ROOT / "prism" / "cli" / "memory.py"
spec = importlib.util.spec_from_file_location("prism.cli.memory_mod", MEM_FILE)
mem_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mem_mod)

memory = mem_mod.memory


def test_memory_disable_embeddings_shows_success(monkeypatch):
    called = {}

    def fake_configure(*args, **kwargs):
        called['configured'] = True

    monkeypatch.setattr(mem_mod.persistent_memory, 'configure_embeddings', fake_configure)

    runner = CliRunner()
    result = runner.invoke(memory, ['disable-embeddings'])
    assert result.exit_code == 0
    assert '语义检索已关闭' in result.output
    assert called.get('configured') is True


def test_memory_status_reports_unconfigured_by_default():
    try:
        mem_mod.persistent_memory.configure_embeddings(base_url='', api_key='', model='')
    except ValueError:
        pass
    mem_mod.persistent_memory._embedding_index._client = None
    mem_mod.persistent_memory._embedding_index._model = ''

    runner = CliRunner()
    result = runner.invoke(memory, ['status'])
    assert result.exit_code == 0
    assert '未启用' in result.output
