"""
PRISM Agent - Prompt 链/工作流编排
多步 prompt 串成 pipeline，自动传参
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CHAIN_DIR = Path.home() / ".prism" / "chains"
_CHAIN_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ChainStep:
    name: str
    prompt: str = ""
    output_key: str = ""
    next_step: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "prompt": self.prompt,
            "output_key": self.output_key,
            "next_step": self.next_step,
        }


@dataclass
class PromptChain:
    name: str
    steps: List[ChainStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
        }


class PromptChainOrchestrator:
    def __init__(self) -> None:
        self._chains: Dict[str, PromptChain] = {}
        self._load()

    def _load(self) -> None:
        for chain_file in _CHAIN_DIR.glob("*.json"):
            try:
                data = json.loads(chain_file.read_text(encoding="utf-8"))
                chain = PromptChain(
                    name=data.get("name", ""),
                    steps=[ChainStep(**s) for s in data.get("steps", [])],
                )
                self._chains[chain.name] = chain
            except Exception:
                continue

    def create(self, chain: PromptChain) -> PromptChain:
        self._chains[chain.name] = chain
        self._save(chain)
        return chain

    def get(self, name: str) -> Optional[PromptChain]:
        return self._chains.get(name)

    def run(self, name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        chain = self._chains.get(name)
        if not chain:
            return {"success": False, "error": f"chain not found: {name}"}
        outputs: Dict[str, Any] = dict(context)
        current_step = chain.steps[0].name if chain.steps else ""
        for step in chain.steps:
            outputs[step.output_key] = step.prompt.format(**outputs)
            current_step = step.next_step or current_step
        return {"success": True, "chain": name, "outputs": outputs}

    def list_chains(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self._chains.values()]

    def _save(self, chain: PromptChain) -> None:
        try:
            (_CHAIN_DIR / f"{chain.name}.json").write_text(
                json.dumps(chain.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


prompt_chain_orchestrator = PromptChainOrchestrator()
