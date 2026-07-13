"""
PRISM Agent - Batch Processing
批量执行 prompt，支持并发度控制、ShareGPT 格式导出、失败自动重试。
"""

from __future__ import annotations

import asyncio
import json
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
        self._results: List[BatchResult] = []

    async def run(self, items: List[BatchItem]) -> List[BatchResult]:
        if not items:
            return []
        semaphore = asyncio.Semaphore(self.max_workers)
        tasks = []
        for idx, item in enumerate(items):
            tasks.append(self._process_item(idx, item, semaphore))
        self._results = list(await asyncio.gather(*tasks))
        return list(self._results)

    async def _process_item(self, idx: int, item: BatchItem, semaphore: asyncio.Semaphore) -> BatchResult:
        last_err = ""
        for attempt in range(1 + self.retry):
            try:
                async with semaphore:
                    agent = self.agent_factory(f"batch-{idx}")
                    content = await asyncio.get_running_loop().run_in_executor(None, agent.chat, item.prompt)
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
