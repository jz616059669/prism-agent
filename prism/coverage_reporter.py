"""
PRISM Agent - 代码覆盖率报告
本地生成 HTML 覆盖率报告
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_COVERAGE_DIR = Path.home() / ".prism" / "coverage"
_COVERAGE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class CoverageReport:
    name: str
    lines: int = 0
    covered: int = 0
    missing: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "lines": self.lines,
            "covered": self.covered,
            "missing": list(self.missing),
            "pct": round(self.covered / self.lines * 100, 1) if self.lines else 0.0,
        }


class CoverageReporter:
    def generate_html(self, reports: List[CoverageReport], output_path: Optional[str] = None) -> str:
        out = output_path or str(_COVERAGE_DIR / "index.html")
        rows = "".join(
            f"<tr><td>{r.name}</td><td>{r.lines}</td><td>{r.covered}</td><td>{', '.join(r.missing)}</td></tr>"
            for r in reports
        )
        html = f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>Coverage</title></head><body><h1>Coverage</h1><table border='1'><tr><th>name</th><th>lines</th><th>covered</th><th>missing</th></tr>{rows}</table></body></html>"
        try:
            Path(out).write_text(html, encoding="utf-8")
        except Exception:
            pass
        return out

    def report_from_pytest(self, coverage_json_path: str) -> List[CoverageReport]:
        path = Path(coverage_json_path)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            reports: List[CoverageReport] = []
            for file_path, info in data.get("files", {}).items():
                summary = info.get("summary", {})
                reports.append(CoverageReport(
                    name=file_path,
                    lines=int(summary.get("num_statements", 0)),
                    covered=int(summary.get("covered_lines", 0)),
                    missing=[str(x) for x in info.get("missing_lines", [])[:20]],
                ))
            return reports
        except Exception:
            return []


coverage_reporter = CoverageReporter()
