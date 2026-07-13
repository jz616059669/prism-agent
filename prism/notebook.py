"""
PRISM Agent - Jupyter Notebook Mode
代码块逐 cell 执行，变量检查，可视化输出
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from prism.sandbox import run_sandbox

logger = logging.getLogger(__name__)


@dataclass
class NotebookCell:
    code: str
    output: str = ""
    plots: List[str] = field(default_factory=list)
    error: str = ""
    variables: Dict[str, Any] = field(default_factory=dict)


class Notebook:
    def __init__(self) -> None:
        self.cells: List[NotebookCell] = []
        self._globals: Dict[str, Any] = {}

    def run_cell(self, code: str, timeout: int = 30) -> NotebookCell:
        cell = NotebookCell(code=code)
        result = run_sandbox(code, timeout=timeout)
        cell.output = result.get("output", "") or ""
        cell.plots = result.get("plots", []) or []
        cell.error = result.get("error", "") or ""
        self.cells.append(cell)
        return cell

    def clear_outputs(self) -> None:
        for cell in self.cells:
            cell.output = ""
            cell.plots = []
            cell.error = ""

    def to_markdown(self) -> str:
        lines: List[str] = []
        for i, cell in enumerate(self.cells, 1):
            lines.append(f"```python\n{cell.code}\n```")
            if cell.error:
                lines.append(f"❌ {cell.error}")
            elif cell.output:
                lines.append(cell.output)
            for plot in cell.plots:
                lines.append(f"![plot]({plot})")
            lines.append("")
        return "\n".join(lines)


notebook = Notebook()
