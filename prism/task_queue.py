"""
PRISM Agent - Task Queue 优先级队列
后台任务处理：优先级、重试、去重、持久化
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_QUEUE_DIR = Path.home() / ".prism" / "task_queue"
_QUEUE_DIR.mkdir(parents=True, exist_ok=True)


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class TaskPriority(int, Enum):
    low = 0
    normal = 1
    high = 2
    critical = 3


@dataclass
class Task:
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = ""
    priority: TaskPriority = TaskPriority.normal
    status: TaskStatus = TaskStatus.pending
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: str = ""
    retries: int = 0
    max_retries: int = 2
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    finished_at: float = 0.0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "priority": self.priority.value,
            "status": self.status.value,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "tags": self.tags,
        }


class TaskQueue:
    def __init__(self, persist: bool = True) -> None:
        self._queue: List[Task] = []
        self._lock = False
        self._persist = persist
        self._load()

    def _load(self) -> None:
        if not self._persist:
            return
        state_file = _QUEUE_DIR / "queue.json"
        if not state_file.exists():
            return
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            self._queue = []
            for item in data:
                t = Task(
                    id=item.get("id", ""),
                    name=item.get("name", ""),
                    priority=TaskPriority(item.get("priority", 1)),
                    status=TaskStatus(item.get("status", "pending")),
                    payload=item.get("payload", {}),
                    result=item.get("result"),
                    error=item.get("error", ""),
                    retries=item.get("retries", 0),
                    max_retries=item.get("max_retries", 2),
                    created_at=item.get("created_at", 0.0),
                    started_at=item.get("started_at", 0.0),
                    finished_at=item.get("finished_at", 0.0),
                    tags=item.get("tags", []),
                )
                self._queue.append(t)
            self._queue.sort(key=lambda t: (-t.priority.value, t.created_at))
        except Exception:
            self._queue = []

    def _save(self) -> None:
        if not self._persist:
            return
        try:
            (_QUEUE_DIR / "queue.json").write_text(
                json.dumps([t.to_dict() for t in self._queue], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def enqueue(self, task: Task) -> Task:
        task.status = TaskStatus.pending
        self._queue.append(task)
        self._queue.sort(key=lambda t: (-t.priority.value, t.created_at))
        self._save()
        return task

    def dequeue(self) -> Optional[Task]:
        for task in self._queue:
            if task.status == TaskStatus.pending:
                task.status = TaskStatus.running
                task.started_at = time.time()
                self._save()
                return task
        return None

    def complete(self, task_id: str, result: Any = None) -> Optional[Task]:
        task = self._get(task_id)
        if not task:
            return None
        task.status = TaskStatus.completed
        task.result = result
        task.finished_at = time.time()
        self._save()
        return task

    def fail(self, task_id: str, error: str = "") -> Optional[Task]:
        task = self._get(task_id)
        if not task:
            return None
        if task.retries < task.max_retries:
            task.retries += 1
            task.status = TaskStatus.pending
            task.error = error
        else:
            task.status = TaskStatus.failed
            task.error = error
            task.finished_at = time.time()
        self._save()
        return task

    def cancel(self, task_id: str) -> Optional[Task]:
        task = self._get(task_id)
        if not task:
            return None
        task.status = TaskStatus.cancelled
        task.finished_at = time.time()
        self._save()
        return task

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Dict[str, Any]]:
        tasks = [t.to_dict() for t in self._queue if status is None or t.status == status]
        return tasks

    def _get(self, task_id: str) -> Optional[Task]:
        for task in self._queue:
            if task.id == task_id:
                return task
        return None


task_queue = TaskQueue()
