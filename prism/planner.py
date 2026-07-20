"""
PRISM Agent - 自主规划模块
复杂任务拆解为多步子任务，失败后自动 replan。
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("prism.planning")


@dataclass
class SubTask:
    """子任务"""
    id: str
    description: str
    status: str = "pending"  # pending / running / done / failed / skipped
    result: Optional[Dict[str, Any]] = None
    retries: int = 0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


@dataclass
class Plan:
    """任务计划"""
    goal: str
    subtasks: List[SubTask] = field(default_factory=list)
    status: str = "active"  # active / completed / failed / replanning
    current_index: int = 0
    created_at: float = field(default_factory=time.time)
    context: Dict[str, Any] = field(default_factory=dict)


class Planner:
    """轻量级自主规划器"""

    def __init__(self, max_steps: int = 6, max_retries: int = 2):
        self.max_steps = max_steps
        self.max_retries = max_retries

    def decompose(self, goal: str) -> Plan:
        """将目标拆成子任务；失败/异常时回退为单步计划"""
        try:
            subtasks = self._llm_decompose(goal)
        except Exception as exc:
            logger.debug("plan decomposition failed: %s", exc)
            subtasks = [SubTask(id="s1", description=goal)]

        plan = Plan(goal=goal, subtasks=subtasks[: self.max_steps])
        return plan

    def next_task(self, plan: Plan) -> Optional[SubTask]:
        """取下一个待执行子任务"""
        if plan.status != "active":
            return None
        for task in plan.subtasks:
            if task.status == "pending":
                return task
        return None

    def mark_done(self, plan: Plan, task: SubTask, result: Dict[str, Any]) -> None:
        task.status = "done"
        task.result = result
        task.finished_at = time.time()
        plan.context[f"result:{task.id}"] = result

    def mark_failed(self, plan: Plan, task: SubTask, error: str) -> Optional[Plan]:
        task.result = {"success": False, "error": error}
        task.finished_at = time.time()
        if task.retries < self.max_retries:
            task.retries += 1
            task.status = "pending"
            logger.info("retry task %s, attempt %d", task.id, task.retries + 1)
            return plan
        task.status = "failed"
        return self._replan(plan, task, error)

    def _replan(self, plan: Plan, failed_task: SubTask, error: str) -> Optional[Plan]:
        """失败后重规划：根据错误尝试新路径"""
        logger.info("replan after %s failed: %s", failed_task.id, error)
        new_plan = Plan(
            goal=plan.goal,
            subtasks=[],
            status="active",
            context=dict(plan.context),
        )
        new_plan.context["last_error"] = error
        new_plan.context["failed_task"] = failed_task.id
        try:
            new_plan.subtasks = self._llm_decompose(
                f"{plan.goal}\n注意：之前执行失败，错误：{error}"
            )[: self.max_steps]
        except Exception:
            new_plan.subtasks = [SubTask(id="s1", description=plan.goal)]
        return new_plan

    def summarize(self, plan: Plan) -> str:
        """把计划执行结果压缩成可交付的最终回复"""
        lines = [f"目标：{plan.goal}"]
        for task in plan.subtasks:
            mark = "✓" if task.status == "done" else ("✗" if task.status == "failed" else "-")
            line = f"{mark} {task.description}"
            if task.result and task.result.get("success"):
                content = task.result.get("content") or task.result.get("text") or ""
                if content:
                    line += f" -> {str(content)[:120]}"
            lines.append(line)
        return "\n".join(lines)

    def _llm_decompose(self, goal: str) -> List[SubTask]:
        """用模型把目标拆成子任务；fallback 为单步"""
        try:
            from prism.agent import create_agent
            agent = create_agent()
            format_hint = '[{"id":"s1","description":"..."}, ...]'
            prompt = (
                "请把下面的目标拆成最多 3 个可执行的子任务，只输出 JSON 数组，不要输出其他内容。"
                "\n目标：{goal}\n\n格式：{fmt}"
            ).format(goal=goal, fmt=format_hint)
            raw = agent.chat(prompt)
            data = json.loads(raw.strip())
            tasks = []
            for idx, item in enumerate(data, 1):
                tasks.append(
                    SubTask(
                        id=item.get("id") or f"s{idx}",
                        description=item.get("description") or goal,
                    )
                )
            return tasks or [SubTask(id="s1", description=goal)]
        except Exception:
            return [SubTask(id="s1", description=goal)]
