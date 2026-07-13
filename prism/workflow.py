"""
PRISM Agent - Workflow Visualizer
预定义工作流：可视化步骤、角色、执行结果
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from prism.orchestrator import TaskOrchestrator, RoleAgent

logger = logging.getLogger(__name__)

_WORKFLOW_DIR = Path.home() / ".prism" / "workflows"
_WORKFLOW_FILE = _WORKFLOW_DIR / "workflows.json"


@dataclass
class WorkflowStep:
    id: str
    role: str
    task: str
    depends_on: List[str] = field(default_factory=list)


@dataclass
class Workflow:
    name: str
    description: str = ""
    steps: List[WorkflowStep] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


def _ensure_workflow_dir() -> None:
    try:
        _WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _default_workflows() -> List[Dict[str, Any]]:
    return [
        {
            "name": "小说调研+大纲",
            "description": "调研题材 -> 生成大纲 -> 审阅",
            "steps": [
                {"id": "s1", "role": "researcher", "task": "调研当前网文平台流行元素和读者偏好", "depends_on": []},
                {"id": "s2", "role": "writer", "task": "基于调研结果生成小说大纲，包含主线、副线和人物设定", "depends_on": ["s1"]},
                {"id": "s3", "role": "reviewer", "task": "审阅大纲，检查逻辑漏洞和吸引力", "depends_on": ["s2"]},
            ],
        },
        {
            "name": "代码审查",
            "description": "编写代码 -> 审查 -> 优化建议",
            "steps": [
                {"id": "s1", "role": "coder", "task": "编写代码实现需求", "depends_on": []},
                {"id": "s2", "role": "reviewer", "task": "审查代码，检查安全和性能问题", "depends_on": ["s1"]},
            ],
        },
        {
            "name": "深度研究",
            "description": "多角度研究 -> 综合分析",
            "steps": [
                {"id": "s1", "role": "researcher", "task": "从技术角度研究主题", "depends_on": []},
                {"id": "s2", "role": "researcher", "task": "从商业角度研究主题", "depends_on": []},
                {"id": "s3", "role": "writer", "task": "整合多角度研究结果，输出综合分析报告", "depends_on": ["s1", "s2"]},
            ],
        },
    ]


def _load_workflows() -> List[Workflow]:
    _ensure_workflow_dir()
    if not _WORKFLOW_FILE.exists():
        data = _default_workflows()
        try:
            _WORKFLOW_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        return [_from_dict(d) for d in data]
    try:
        data = json.loads(_WORKFLOW_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [_from_dict(d) for d in data if isinstance(d, dict)]
    except Exception as exc:
        logger.debug("load workflows failed: %s", exc)
    return []


def _from_dict(data: Dict[str, Any]) -> Workflow:
    steps = []
    for s in data.get("steps", []):
        if isinstance(s, dict):
            steps.append(WorkflowStep(
                id=str(s.get("id", "")),
                role=str(s.get("role", "")),
                task=str(s.get("task", "")),
                depends_on=[str(x) for x in (s.get("depends_on") or [])],
            ))
    return Workflow(
        name=str(data.get("name", "")),
        description=str(data.get("description", "") or ""),
        steps=steps,
        metadata={k: v for k, v in data.items() if k not in {"name", "description", "steps"}},
    )


def _to_dict(wf: Workflow) -> Dict[str, Any]:
    return {
        "name": wf.name,
        "description": wf.description,
        "steps": [
            {
                "id": s.id,
                "role": s.role,
                "task": s.task,
                "depends_on": s.depends_on,
            }
            for s in wf.steps
        ],
        "metadata": wf.metadata,
    }


def list_workflows() -> List[Dict[str, Any]]:
    return [_to_dict(w) for w in _load_workflows()]


def get_workflow(name: str) -> Optional[Dict[str, Any]]:
    for wf in _load_workflows():
        if wf.name == name:
            return _to_dict(wf)
    return None


def run_workflow(name: str, parent_agent: Any, max_parallel: int = 3) -> Dict[str, Any]:
    wf = next((w for w in _load_workflows() if w.name == name), None)
    if not wf:
        return {"success": False, "error": f"workflow not found: {name}"}
    orchestrator = TaskOrchestrator(max_parallel=max_parallel)
    user_message = _workflow_to_prompt(wf)
    try:
        result = orchestrator.orchestrate(user_message, parent_agent)
        return {"success": True, "result": result, "workflow": name}
    except Exception as exc:
        logger.debug("run workflow failed: %s", exc)
        return {"success": False, "error": str(exc), "workflow": name}


def _workflow_to_prompt(wf: Workflow) -> str:
    lines = [f"执行工作流：{wf.name}"]
    if wf.description:
        lines.append(f"说明：{wf.description}")
    lines.append("步骤：")
    for s in wf.steps:
        deps = f"（依赖：{', '.join(s.depends_on)}）" if s.depends_on else ""
        lines.append(f"- [{s.role}] {s.task} {deps}")
    lines.append("请按步骤执行并给出最终结果。")
    return "\n".join(lines)
