"""
PRISM Agent - Data Pipeline
本地 ETL：CSV/JSON/SQLite 转换+清洗
"""

from __future__ import annotations

import csv
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    success: bool
    rows: int = 0
    output_path: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "rows": self.rows,
            "output_path": self.output_path,
            "error": self.error,
        }


class DataPipeline:
    def csv_to_json(self, csv_path: str, json_path: str) -> PipelineResult:
        csv_file = Path(csv_path)
        if not csv_file.exists():
            return PipelineResult(success=False, error="csv not found")
        try:
            rows: List[Dict[str, Any]] = []
            with csv_file.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rows.append(dict(row))
            Path(json_path).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            return PipelineResult(success=True, rows=len(rows), output_path=json_path)
        except Exception as exc:
            return PipelineResult(success=False, error=str(exc))

    def json_to_csv(self, json_path: str, csv_path: str) -> PipelineResult:
        path = Path(json_path)
        if not path.exists():
            return PipelineResult(success=False, error="json not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return PipelineResult(success=False, error="json root must be array")
            keys = sorted({k for row in data if isinstance(row, dict) for k in row.keys()})
            with Path(csv_path).open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for row in data:
                    writer.writerow({k: row.get(k, "") for k in keys})
            return PipelineResult(success=True, rows=len(data), output_path=csv_path)
        except Exception as exc:
            return PipelineResult(success=False, error=str(exc))

    def json_to_sqlite(self, json_path: str, sqlite_path: str, table: str = "items") -> PipelineResult:
        path = Path(json_path)
        if not path.exists():
            return PipelineResult(success=False, error="json not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return PipelineResult(success=False, error="json root must be array")
            keys = sorted({k for row in data if isinstance(row, dict) for k in row.keys()})
            conn = sqlite3.connect(sqlite_path)
            cur = conn.cursor()
            cur.execute(f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(['`' + k + '` TEXT' for k in keys])})")
            for row in data:
                values = [str(row.get(k, "")) for k in keys]
                cur.execute(f"INSERT INTO {table} VALUES ({','.join(['?'] * len(values))})", values)
            conn.commit()
            conn.close()
            return PipelineResult(success=True, rows=len(data), output_path=sqlite_path)
        except Exception as exc:
            return PipelineResult(success=False, error=str(exc))

    def clean_json(self, json_path: str, remove_nulls: bool = True, dedupe: bool = True) -> PipelineResult:
        path = Path(json_path)
        if not path.exists():
            return PipelineResult(success=False, error="json not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return PipelineResult(success=False, error="json root must be array")
            cleaned: List[Dict[str, Any]] = []
            seen: List[Dict[str, Any]] = []
            for row in data:
                if not isinstance(row, dict):
                    continue
                if remove_nulls:
                    row = {k: v for k, v in row.items() if v is not None and v != ""}
                if dedupe:
                    if row in seen:
                        continue
                    seen.append(row)
                cleaned.append(row)
            path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
            return PipelineResult(success=True, rows=len(cleaned), output_path=str(path))
        except Exception as exc:
            return PipelineResult(success=False, error=str(exc))


data_pipeline = DataPipeline()
