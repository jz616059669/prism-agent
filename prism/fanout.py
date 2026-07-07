"""
PRISM background fan-out — parallel subagent execution.
Spawns multiple subagents concurrently for research, drafting, or review.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional


class BackgroundFanOut:
    """Run multiple subagent tasks in parallel and collect results."""

    def __init__(self, agent_factory: Callable[[str], Any]):
        self.agent_factory = agent_factory
        self._results: Dict[str, Any] = {}
        self._threads: Dict[str, threading.Thread] = {}

    def run(self, tasks: Dict[str, str]) -> Dict[str, Any]:
        """Run tasks in parallel.
        
        Args:
            tasks: mapping of subagent name -> task prompt
            
        Returns:
            mapping of name -> result dict
        """
        results: Dict[str, Any] = {}
        threads: Dict[str, threading.Thread] = {}

        def _worker(name: str, prompt: str) -> None:
            try:
                agent = self.agent_factory(name)
                output = agent.chat(prompt)
                results[name] = {"success": True, "name": name, "output": output}
            except Exception as exc:  # noqa: BLE001
                results[name] = {"success": False, "name": name, "error": str(exc)}

        for name, prompt in tasks.items():
            t = threading.Thread(target=_worker, args=(name, prompt), daemon=True)
            threads[name] = t
            t.start()

        for t in threads.values():
            t.join(timeout=180)

        self._results = results
        return results

    def aggregate(self, results: Optional[Dict[str, Any]] = None) -> str:
        """Aggregate parallel results into one summary string."""
        results = results or self._results
        parts: List[str] = []
        for name, res in results.items():
            if res.get("success"):
                parts.append(f"[{name}] {res.get('output', '')}")
            else:
                parts.append(f"[{name}] ERROR: {res.get('error', '')}")
        return "\n\n".join(parts)
