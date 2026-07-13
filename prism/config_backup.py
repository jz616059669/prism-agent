"""
PRISM Agent - 配置导入/导出
一键备份恢复
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BACKUP_DIR = Path.home() / ".prism" / "backups"
_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class BackupResult:
    success: bool
    path: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "path": self.path,
            "error": self.error,
        }


class ConfigBackup:
    def export_config(self, output_path: Optional[str] = None) -> BackupResult:
        output_path = output_path or str(_BACKUP_DIR / f"config_backup_{int(__import__('time').time())}.json")
        try:
            from prism.config import get_config
            cfg = get_config()
            data = cfg.show(redact=False)
            Path(output_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return BackupResult(success=True, path=output_path)
        except Exception as exc:
            return BackupResult(success=False, error=str(exc))

    def import_config(self, backup_path: str) -> BackupResult:
        path = Path(backup_path)
        if not path.exists():
            return BackupResult(success=False, error="backup not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            from prism.config import get_config
            cfg = get_config()
            cfg._config = data
            cfg._save()
            return BackupResult(success=True, path=backup_path)
        except Exception as exc:
            return BackupResult(success=False, error=str(exc))


config_backup = ConfigBackup()
