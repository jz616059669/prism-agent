"""
PRISM Agent - 多智能体协作
Supervisor / Worker 模式：复杂任务拆给子 agent 并行/串行执行，再汇总。
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("prism.multi_agent")


@dataclass
class WorkerResult:
    worker_id: str
    task: str
    result: str
    success: bool
    error: Optional[str] = None


class Supervisor:
    """主管智能体：负责任务分发与结果汇总"""

    def __init__(self, max_workers: int = 2):
        self.max_workers = max_workers
        self._workers: Dict[str, Any] = {}

    def spawn_worker(self, worker_id: str, system_prompt: Optional[str] = None) -> Any:
        try:
            from prism.agent import create_agent
            self._workers[worker_id] = create_agent(system_prompt=system_prompt)
            return self._workers[worker_id]
        except Exception as exc:
            logger.debug("spawn worker failed: %s", exc)
            return None

    def dispatch(self, tasks: List[Dict[str, str]], parallel: bool = False) -> List[WorkerResult]:
        if not tasks:
            return []
        if parallel:
            return self._dispatch_parallel(tasks)
        return self._dispatch_serial(tasks)

    def summarize(self, goal: str, results: List[WorkerResult]) -> str:
        lines = [f"主管总结：{goal}"]
        for r in results:
            mark = "✓" if r.success else "✗"
            lines.append(f"{mark} worker={r.worker_id} task={r.task}")
            if r.success and r.result:
                lines.append(f"  -> {r.result[:200]}")
            elif r.error:
                lines.append(f"  !! {r.error[:120]}")
        return "\n".join(lines)

    def _dispatch_serial(self, tasks: List[Dict[str, str]]) -> List[WorkerResult]:
        results: List[WorkerResult] = []
        for idx, task in enumerate(tasks, 1):
            worker_id = task.get("worker_id") or f"w{idx}"
            prompt = task.get("prompt") or task.get("task") or ""
            worker = self._workers.get(worker_id)
            if worker is None:
                worker = self.spawn_worker(worker_id, task.get("system_prompt"))
            if worker is None:
                results.append(WorkerResult(worker_id=worker_id, task=prompt, result="", success=False, error="worker unavailable"))
                continue
            try:
                answer = worker.chat(prompt)
                results.append(WorkerResult(worker_id=worker_id, task=prompt, result=answer or "", success=True))
            except Exception as exc:
                results.append(WorkerResult(worker_id=worker_id, task=prompt, result="", success=False, error=str(exc)))
        return results

    def _dispatch_parallel(self, tasks: List[Dict[str, str]]) -> List[WorkerResult]:
        results: List[WorkerResult] = []
        lock = threading.Lock()

        def _run(task: Dict[str, str], idx: int) -> None:
            worker_id = task.get("worker_id") or f"w{idx}"
            prompt = task.get("prompt") or task.get("task") or ""
            worker = self._workers.get(worker_id)
            if worker is None:
                worker = self.spawn_worker(worker_id, task.get("system_prompt"))
            if worker is None:
                with lock:
                    results.append(WorkerResult(worker_id=worker_id, task=prompt, result="", success=False, error="worker unavailable"))
                return
            try:
                answer = worker.chat(prompt)
                with lock:
                    results.append(WorkerResult(worker_id=worker_id, task=prompt, result=answer or "", success=True))
            except Exception as exc:
                with lock:
                    results.append(WorkerResult(worker_id=worker_id, task=prompt, result="", success=False, error=str(exc)))

        threads = []
        for idx, task in enumerate(tasks, 1):
            t = threading.Thread(target=_run, args=(task, idx), daemon=True)
            threads.append(t)
            t.start()
        for t in threads:
            t.join(timeout=120)
        return results
