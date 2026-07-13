"""
PRISM Agent - 对话搜索
全文搜索历史对话
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SEARCH_DIR = Path.home() / ".prism" / "search"
_SEARCH_DIR.mkdir(parents=True, exist_ok=True)


class ConversationSearch:
    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        results = []
        q = (query or "").lower().strip()
        if not q:
            return results
        try:
            for msg_file in _SEARCH_DIR.glob("*.jsonl"):
                try:
                    for line in msg_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                        if not line.strip():
                            continue
                        data = json.loads(line)
                        content = str(data.get("content", "") or "")
                        if q in content.lower():
                            data["_file"] = str(msg_file)
                            results.append(data)
                except Exception:
                    continue
        except Exception:
            pass
        return results[-limit:]


conversation_search = ConversationSearch()
