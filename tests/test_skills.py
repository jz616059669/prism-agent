"""
PRISM Agent - Skills 系统测试
覆盖：内置 skills、安装/卸载、搜索
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.skills import skills


def test_builtin_skills_loaded():
    skill_list = skills.list_skills()
    names = {s['name'] for s in skill_list}
    assert 'file_operations' in names
    assert 'terminal_execution' in names
    assert 'web_search' in names
    assert 'code_execution' in names
    assert 'novel_writing' in names
    assert 'novel_optimization' in names


def test_skill_search_chinese():
    matches = skills.match("读取文件")
    assert any(s.name == 'file_operations' for s in matches)


def test_skill_search_english():
    matches = skills.match("search web")
    assert any(s.name == 'web_search' for s in matches)


def test_skill_search_partial():
    matches = skills.match("帮我写个小说章节")
    assert any(s.name == 'novel_writing' for s in matches)


def test_skill_install_fails_without_hub():
    try:
        import prism.gateway.feishu as feishu_mod
    except Exception:
        feishu_mod = None
    import prism.config as config_mod
    old = getattr(config_mod.config, '_config', {})
    try:
        config_mod.config._config = dict(old)
        config_mod.config._config.pop('skills', None)
        if feishu_mod is not None:
            feishu_mod.prism_config = config_mod.config
        result = skills.install_skill("nonexistent_skill")
        assert result['success'] is False
    finally:
        config_mod.config._config = old
        if feishu_mod is not None:
            feishu_mod.prism_config = config_mod.config


def test_skill_uninstall_not_installed():
    result = skills.uninstall_skill("nonexistent_skill")
    assert result['success'] is True
