"""
PRISM Agent - 配置漂移检测
对比 config.yaml 与默认值，检测被非法/意外修改的项
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DriftItem:
    key: str
    expected: Any = None
    actual: Any = None
    severity: str = "info"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "expected": self.expected,
            "actual": self.actual,
            "severity": self.severity,
        }


class ConfigDriftDetector:
    def __init__(self, config_obj: Any) -> None:
        self.config = config_obj

    def detect(self) -> List[DriftItem]:
        drifts: List[DriftItem] = []
        try:
            defaults = self.config._defaults()
            current = self.config.show(redact=False)
            self._compare("", defaults, current, drifts)
        except Exception as exc:
            logger.debug("drift detect failed: %s", exc)
        return drifts

    def _compare(self, prefix: str, expected: Any, actual: Any, drifts: List[DriftItem]) -> None:
        if isinstance(expected, dict) and isinstance(actual, dict):
            for key in set(expected) | set(actual):
                path = f"{prefix}.{key}" if prefix else key
                exp_val = expected.get(key)
                act_val = actual.get(key)
                if exp_val is None and act_val is not None:
                    drifts.append(DriftItem(key=path, expected=exp_val, actual=act_val, severity="warning"))
                elif exp_val is not None and act_val is None:
                    drifts.append(DriftItem(key=path, expected=exp_val, actual=act_val, severity="warning"))
                elif isinstance(exp_val, dict) and isinstance(act_val, dict):
                    self._compare(path, exp_val, act_val, drifts)
                elif exp_val != act_val:
                    drifts.append(DriftItem(key=path, expected=exp_val, actual=act_val, severity="info"))
        elif expected != actual:
            path = prefix or "value"
            drifts.append(DriftItem(key=path, expected=expected, actual=actual, severity="info"))


config_drift_detector = ConfigDriftDetector(None)
