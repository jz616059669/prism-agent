"""
PRISM Agent - 语音克隆样本管理
录制用户声音样本，用于后续个性化 TTS
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_VOICE_DIR = Path.home() / ".prism" / "voice_samples"
_VOICE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class VoiceSample:
    id: str
    label: str = ""
    path: str = ""
    duration: float = 0.0
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "path": self.path,
            "duration": self.duration,
            "created_at": self.created_at,
        }


class VoiceCloneStore:
    def __init__(self) -> None:
        self._samples: Dict[str, VoiceSample] = {}
        self._load()

    def _load(self) -> None:
        for sample_file in _VOICE_DIR.glob("*.json"):
            try:
                data = json.loads(sample_file.read_text(encoding="utf-8"))
                sample = VoiceSample(**data)
                self._samples[sample.id] = sample
            except Exception:
                continue

    def add(self, sample: VoiceSample) -> VoiceSample:
        self._samples[sample.id] = sample
        self._save(sample)
        return sample

    def list_samples(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._samples.values()]

    def _save(self, sample: VoiceSample) -> None:
        try:
            (_VOICE_DIR / f"{sample.id}.json").write_text(
                json.dumps(sample.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    def remove(self, sample_id: str) -> bool:
        if sample_id not in self._samples:
            return False
        del self._samples[sample_id]
        try:
            (_VOICE_DIR / f"{sample_id}.json").unlink()
        except Exception:
            pass
        return True


voice_clone_store = VoiceCloneStore()
