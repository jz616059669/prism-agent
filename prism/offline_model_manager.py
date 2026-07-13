"""
PRISM Agent - 离线模型管理
本地模型下载/切换/版本管理
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

_MODEL_DIR = Path.home() / ".prism" / "models"
_MODEL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ModelInfo:
    name: str
    version: str = "latest"
    path: str = ""
    size_mb: float = 0.0
    active: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "path": self.path,
            "size_mb": round(self.size_mb, 1),
            "active": self.active,
            "created_at": self.created_at,
        }


class OfflineModelManager:
    def __init__(self) -> None:
        self._models: Dict[str, ModelInfo] = {}
        self._load()

    def _load(self) -> None:
        for model_file in _MODEL_DIR.glob("*.json"):
            try:
                data = json.loads(model_file.read_text(encoding="utf-8"))
                model = ModelInfo(**data)
                self._models[model.name] = model
            except Exception:
                continue

    def register(self, name: str, version: str = "latest", path: str = "", size_mb: float = 0.0) -> ModelInfo:
        model = ModelInfo(name=name, version=version, path=path, size_mb=size_mb)
        self._models[name] = model
        self._save(model)
        return model

    def set_active(self, name: str) -> Optional[ModelInfo]:
        model = self._models.get(name)
        if not model:
            return None
        for m in self._models.values():
            m.active = False
            self._save(m)
        model.active = True
        self._save(model)
        return model

    def list_models(self) -> List[Dict[str, Any]]:
        return [m.to_dict() for m in self._models.values()]

    def active_model(self) -> Optional[Dict[str, Any]]:
        for m in self._models.values():
            if m.active:
                return m.to_dict()
        return None

    def _save(self, model: ModelInfo) -> None:
        try:
            (_MODEL_DIR / f"{model.name}.json").write_text(
                json.dumps(model.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass


offline_model_manager = OfflineModelManager()
