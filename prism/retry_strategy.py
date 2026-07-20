"""
PRISM Agent - 任务重试策略
失败自动重试，指数退避
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_RETRY_DIR = Path.home() / ".prism" / "retry"
_RETRY_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class RetryTask:
    id: str
    func: str = ""
    args: List[Any] = field(default_factory=list)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    attempts: int = 0
    max_attempts: int = 3
    backoff: float = 1.0
    next_ts: float = 0.0
    last_error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "func": self.func,
            "args": self.args,
            "kwargs": self.kwargs,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "backoff": self.backoff,
            "next_ts": self.next_ts,
            "last_error": self.last_error,
        }


class RetryStrategy:
    def __init__(self) -> None:
        self._tasks: Dict[str, RetryTask] = {}
        self._load()
        self._lock = __import__("threading").Lock()
        self._executor_thread: Optional[Any] = None
        self._running = False

    def start(self) -> Optional[threading.Thread]:
        if self._running:
            return self._executor_thread
        self._running = True
        self._executor_thread = threading.Thread(target=self._run_forever, daemon=True)
        self._executor_thread.start()
        return self._executor_thread

    def stop(self) -> None:
        self._running = False

    def _run_forever(self) -> None:
        while self._running:
            try:
                due = self.due()
                for task in due:
                    self._execute(task)
            except Exception:
                logger.debug("retry executor loop error", exc_info=True)
            time.sleep(1.0)

    def _execute(self, task: RetryTask) -> None:
        with self._lock:
            if task.attempts >= task.max_attempts:
                return
            task.attempts += 1
            self._save(task)
        try:
            allowed_funcs = {"terminal", "web_search", "browser_navigate"}
            if task.func in allowed_funcs:
                from prism.tools.registry import registry
                result = registry.execute(task.func, *task.args, **task.kwargs)
                success = result.get("success")
            else:
                raise ValueError(f"unsupported func for auto retry: {task.func}")
            if not success:
                self.record_failure(task.id, error=str(result.get("error")))
        except Exception as exc:
            self.record_failure(task.id, error=str(exc))

    def _load(self) -> None:
        for task_file in _RETRY_DIR.glob("*.json"):
            try:
                data = json.loads(task_file.read_text(encoding="utf-8"))
                task = RetryTask(**data)
                self._tasks[task.id] = task
            except Exception:
                continue

    def submit(self, task_id: str, func: str, args: Optional[List[Any]] = None, kwargs: Optional[Dict[str, Any]] = None, max_attempts: int = 3, backoff: float = 1.0) -> RetryTask:
        task = RetryTask(id=task_id, func=func, args=args or [], kwargs=kwargs or {}, max_attempts=max_attempts, backoff=backoff)
        self._tasks[task_id] = task
        self._save(task)
        return task

    def record_failure(self, task_id: str, error: str = "") -> Optional[RetryTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.attempts += 1
        task.last_error = error
        if task.attempts >= task.max_attempts:
            task.next_ts = 0.0
        else:
            task.next_ts = time.time() + task.backoff * (2 ** (task.attempts - 1))
        self._save(task)
        return task

    def due(self) -> List[RetryTask]:
        now = time.time()
        return [task for task in self._tasks.values() if task.next_ts and task.next_ts <= now]

    def _save(self, task: RetryTask) -> None:
        try:
            (_RETRY_DIR / f"{task.id}.json").write_text(
                json.dumps(task.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


retry_strategy = RetryStrategy()
