"""
PRISM Agent - Workspace tests
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def test_workspace_manager_lazy_load(tmp_path):
    from prism.workspace import WorkspaceManager
    manager = WorkspaceManager(base_dir=tmp_path)
    assert manager._loaded is False
    workspaces = manager.list_workspaces()
    assert manager._loaded is True
    assert any(ws["name"] == "default" for ws in workspaces)


def test_workspace_create_and_switch(tmp_path):
    from prism.workspace import WorkspaceManager
    manager = WorkspaceManager(base_dir=tmp_path)
    ws = manager.create_workspace("alpha", tmp_path / "alpha", description="alpha ws")
    assert ws.name == "alpha"
    agent = manager.get_agent("alpha")
    assert agent is not None
    agent2 = manager.switch_workspace("alpha")
    assert agent2 is agent


def test_workspace_delete_protects_default(tmp_path):
    from prism.workspace import WorkspaceManager
    manager = WorkspaceManager(base_dir=tmp_path)
    try:
        manager.delete_workspace("default")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError when deleting default workspace")
