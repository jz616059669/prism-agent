"""
PRISM Agent - Batch Processing
批量执行 prompt，支持并行度控制、ShareGPT 格式导出、失败自动重试。
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from prism.logging import logger


@dataclass
class BatchItem:
    prompt: str
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BatchResult:
    index: int
    prompt: str
    success: bool
    content: str = ""
    error: str = ""
    model: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


class BatchProcessor:
    """
    批量处理 prompts。
    - 并发度由 max_workers 控制
    - 每个 item 可附带 meta 字段，最终保留在结果里
    - 返回 ShareGPT 格式轨迹（ conversations 列表）
    """

    def __init__(
        self,
        agent_factory: Callable[[str], Any],
        max_workers: int = 4,
        retry: int = 1,
    ) -> None:
        self.agent_factory = agent_factory
        self.max_workers = max(1, max_workers)
        self.retry = max(0, retry)
        self._lock = threading.Lock()
        self._results: List[BatchResult] = []

    def run(self, items: List[BatchItem]) -> List[BatchResult]:
        results: List[Optional[BatchResult]] = [None] * len(items)
        threads: Dict[int, threading.Thread] = {}

        def _worker(idx: int, item: BatchItem) -> None:
            res = self._process_item(idx, item)
            results[idx] = res

        # 分块调度，避免瞬间起太多线程
        pending = list(range(len(items)))
        active: Dict[int, threading.Thread] = {}
        it = 0
        while pending or active:
            while pending and len(active) < self.max_workers:
                idx = pending.pop(0)
                t = threading.Thread(target=_worker, args=(idx, items[idx]), daemon=True)
                active[idx] = t
                t.start()
            # 等待任意线程结束
            done = [k for k, t in active.items() if not t.is_alive()]
            for k in done:
                active[k].join(timeout=180)
                active.pop(k)
            if not done and active:
                import time
                time.sleep(0.05)

        self._results = [r for r in results if isinstance(r, BatchResult)]
        return self._results

    def _process_item(self, idx: int, item: BatchItem) -> BatchResult:
        last_err = ""
        for attempt in range(1 + self.retry):
            try:
                agent = self.agent_factory(f"batch-{idx}")
                content = agent.chat(item.prompt)
                return BatchResult(
                    index=idx,
                    prompt=item.prompt,
                    success=True,
                    content=content or "",
                    model=getattr(agent, "model", "") or "",
                    meta=item.meta or {},
                )
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
                logger.debug("batch item %d attempt %d failed: %s", idx, attempt, exc)
        return BatchResult(
            index=idx,
            prompt=item.prompt,
            success=False,
            error=last_err,
            meta=item.meta or {},
        )

    def to_sharegpt(self, results: Optional[List[BatchResult]] = None) -> List[Dict[str, Any]]:
        """
        将结果转换为 ShareGPT conversations 格式：
        [
          {
            "conversations": [
              {"from": "human", "value": "<prompt>"},
              {"from": "gpt", "value": "<content>"}
            ]
          }
        ]
        """
        results = results or self._results
        out: List[Dict[str, Any]] = []
        for r in results:
            if not r.success:
                continue
            out.append({
                "conversations": [
                    {"from": "human", "value": r.prompt},
                    {"from": "gpt", "value": r.content},
                ]
            })
        return out

    def summary(self, results: Optional[List[BatchResult]] = None) -> Dict[str, Any]:
        results = results or self._results
        total = len(results)
        ok = sum(1 for r in results if r.success)
        failed = total - ok
        return {
            "total": total,
            "success": ok,
            "failed": failed,
            "success_rate": round(ok / total, 4) if total else 0.0,
        }


__all__ = ["BatchProcessor", "BatchItem", "BatchResult"]
