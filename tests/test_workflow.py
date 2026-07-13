"""
PRISM Agent - Workflow tests
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prism.workflow import Workflow, WorkflowStep, _load_workflows, list_workflows, get_workflow, run_workflow, _workflow_to_prompt


def test_default_workflows_created(tmp_path):
    with patch("prism.workflow._WORKFLOW_DIR", tmp_path), patch("prism.workflow._WORKFLOW_FILE", tmp_path / "workflows.json"):
        wfs = _load_workflows()
        assert len(wfs) >= 3


def test_list_workflows_returns_dicts(tmp_path):
    with patch("prism.workflow._WORKFLOW_DIR", tmp_path), patch("prism.workflow._WORKFLOW_FILE", tmp_path / "workflows.json"):
        wfs = list_workflows()
        assert isinstance(wfs, list)
        assert all(isinstance(w, dict) for w in wfs)


def test_get_workflow_by_name(tmp_path):
    with patch("prism.workflow._WORKFLOW_DIR", tmp_path), patch("prism.workflow._WORKFLOW_FILE", tmp_path / "workflows.json"):
        wf = get_workflow("小说调研+大纲")
        assert wf is not None
        assert wf["name"] == "小说调研+大纲"


def test_workflow_to_prompt():
    wf = Workflow(name="test", description="desc", steps=[WorkflowStep(id="s1", role="coder", task="code", depends_on=[])])
    prompt = _workflow_to_prompt(wf)
    assert "执行工作流：test" in prompt
    assert "[coder] code" in prompt


def test_run_workflow_not_found(tmp_path):
    with patch("prism.workflow._WORKFLOW_DIR", tmp_path), patch("prism.workflow._WORKFLOW_FILE", tmp_path / "workflows.json"):
        res = run_workflow("missing", MagicMock())
        assert res["success"] is False
        assert "not found" in res.get("error", "")
