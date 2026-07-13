"""
PRISM Agent - 对话导出/导入
支持 markdown/pdf/json 格式
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_EXPORT_DIR = Path.home() / ".prism" / "exports"
_EXPORT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ExportResult:
    success: bool
    path: str = ""
    format: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "path": self.path,
            "format": self.format,
            "error": self.error,
        }


class ConversationExporter:
    def export_markdown(self, session_id: str, messages: List[Dict[str, Any]], filename: Optional[str] = None) -> ExportResult:
        lines = [f"# PRISM Conversation - {session_id}\n"]
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            lines.append(f"## {role}\n{content}\n")
        out_path = str(_EXPORT_DIR / f"{filename or session_id}.md")
        try:
            Path(out_path).write_text("\n".join(lines), encoding="utf-8")
            return ExportResult(success=True, path=out_path, format="markdown")
        except Exception as exc:
            return ExportResult(success=False, format="markdown", error=str(exc))

    def export_json(self, session_id: str, messages: List[Dict[str, Any]], filename: Optional[str] = None) -> ExportResult:
        out_path = str(_EXPORT_DIR / f"{filename or session_id}.json")
        try:
            Path(out_path).write_text(
                json.dumps({"session_id": session_id, "messages": messages}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return ExportResult(success=True, path=out_path, format="json")
        except Exception as exc:
            return ExportResult(success=False, format="json", error=str(exc))

    def export_pdf(self, session_id: str, messages: List[Dict[str, Any]], filename: Optional[str] = None) -> ExportResult:
        out_path = str(_EXPORT_DIR / f"{filename or session_id}.pdf")
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            for msg in messages:
                role = msg.get("role", "user")
                content = str(msg.get("content", ""))
                pdf.cell(0, 10, f"{role}:", ln=True)
                pdf.multi_cell(0, 10, content)
                pdf.ln(2)
            pdf.output(out_path)
            return ExportResult(success=True, path=out_path, format="pdf")
        except Exception as exc:
            return ExportResult(success=False, format="pdf", error=str(exc))

    def import_json(self, file_path: str) -> ExportResult:
        path = Path(file_path)
        if not path.exists():
            return ExportResult(success=False, format="json", error="file not found")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            messages = data.get("messages", [])
            return ExportResult(success=True, path=str(path), format="json", error="")
        except Exception as exc:
            return ExportResult(success=False, format="json", error=str(exc))


conversation_exporter = ConversationExporter()
