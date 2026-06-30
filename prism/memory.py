"""
PRISM Agent - Persistent Memory
借鉴 Hermes Agent 的持久记忆机制，支持跨会话的知识积累。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("prism.memory")


@dataclass
class Memory:
    """记忆条目"""
    key: str
    value: str
    category: str = "general"
    confidence: float = 1.0
    source: str = "user"
    created_at: str = ""
    updated_at: str = ""


class PersistentMemory:
    """持久化记忆系统"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or Path.home() / ".prism" / "memory"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index: Dict[str, Memory] = {}
        self._load()

    def _load(self) -> None:
        """从磁盘加载记忆"""
        index_file = self.base_dir / "index.json"
        if not index_file.exists():
            return
        try:
            data = json.loads(index_file.read_text(encoding="utf-8"))
            for item in data.get("memories", []):
                memory = Memory(
                    key=item["key"],
                    value=item["value"],
                    category=item.get("category", "general"),
                    confidence=item.get("confidence", 1.0),
                    source=item.get("source", "user"),
                    created_at=item.get("created_at", ""),
                    updated_at=item.get("updated_at", ""),
                )
                self._index[memory.key] = memory
        except Exception as exc:
            logger.warning("failed to load memory: %s", exc)

    def _save(self) -> None:
        """保存记忆到磁盘"""
        index_file = self.base_dir / "index.json"
        data = {
            "memories": [
                {
                    "key": m.key,
                    "value": m.value,
                    "category": m.category,
                    "confidence": m.confidence,
                    "source": m.source,
                    "created_at": m.created_at,
                    "updated_at": m.updated_at,
                }
                for m in self._index.values()
            ]
        }
        index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def remember(self, key: str, value: str, category: str = "general", confidence: float = 1.0, source: str = "user") -> None:
        """存储记忆"""
        from datetime import datetime
        
        now = datetime.now().isoformat()
        if key in self._index:
            memory = self._index[key]
            memory.value = value
            memory.confidence = max(memory.confidence, confidence)
            memory.updated_at = now
        else:
            memory = Memory(
                key=key,
                value=value,
                category=category,
                confidence=confidence,
                source=source,
                created_at=now,
                updated_at=now,
            )
        self._index[key] = memory
        self._save()
        logger.debug("memory stored: %s", key)

    def recall(self, key: str) -> Optional[str]:
        """回忆记忆"""
        memory = self._index.get(key)
        return memory.value if memory else None

    def forget(self, key: str) -> bool:
        """遗忘记忆"""
        if key in self._index:
            del self._index[key]
            self._save()
            return True
        return False

    def search(self, query: str, category: Optional[str] = None, limit: int = 10) -> List[Memory]:
        """搜索记忆"""
        query_lower = query.lower()
        results = []
        for memory in self._index.values():
            if category and memory.category != category:
                continue
            if query_lower in memory.key.lower() or query_lower in memory.value.lower():
                results.append(memory)
        results.sort(key=lambda m: m.confidence, reverse=True)
        return results[:limit]

    def list_by_category(self, category: str) -> List[Memory]:
        """按类别列出记忆"""
        return [m for m in self._index.values() if m.category == category]

    def get_context(self, max_items: int = 5) -> str:
        """获取记忆上下文，用于注入到系统提示词"""
        memories = sorted(self._index.values(), key=lambda m: m.confidence, reverse=True)[:max_items]
        if not memories:
            return ""
        lines = ["## 记忆上下文"]
        for m in memories:
            lines.append(f"- [{m.category}] {m.key}: {m.value[:100]}")
        return "\n".join(lines)

    def clear(self) -> None:
        """清空所有记忆"""
        self._index.clear()
        self._save()


# 全局记忆实例
memory = PersistentMemory()
