"""
PRISM Agent - Model Fallback Chain
多模型自动故障转移，主备切换
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ModelCandidate:
    name: str
    provider: str = ""
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    max_tokens: int = 4096
    priority: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "priority": self.priority,
        }


class ModelFallbackChain:
    def __init__(self, candidates: Optional[List[ModelCandidate]] = None) -> None:
        self._candidates = sorted(candidates or [], key=lambda c: c.priority, reverse=True)
        self._current_index = 0

    def current(self) -> Optional[ModelCandidate]:
        if not self._candidates:
            return None
        return self._candidates[self._current_index]

    def fallback(self) -> Optional[ModelCandidate]:
        if self._current_index + 1 < len(self._candidates):
            self._current_index += 1
            logger.warning("model fallback to %s", self._current().name if self._current() else "?")
            return self._current()
        return None

    def reset(self) -> None:
        self._current_index = 0

    def list_candidates(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self._candidates]


model_fallback_chain = ModelFallbackChain()
