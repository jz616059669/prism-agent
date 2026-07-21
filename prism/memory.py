"""
PRISM Agent - Enhanced Persistent Memory
基础 KV 记忆 + 可选语义检索 + 记忆摘要压缩
"""

from __future__ import annotations

import json
import logging
import traceback
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from prism.paths import memory_dir
from prism.memory_providers import memory_provider_registry, MemoryProviderRegistry, MemoryRecord

logger = logging.getLogger("prism.memory")


def _now_iso() -> str:
    return datetime.now().isoformat()


def _short(text: str, limit: int = 64) -> str:
    text = text.replace(chr(10), ' ').replace(chr(13), ' ')
    return text[:limit]


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
    embedding: Optional[List[float]] = None
    embedding_model: str = ""
    access_count: int = 0
    last_accessed_at: str = ""
    digest: str = ""
    # 记忆冲突解决
    supersedes_key: str = ""
    conflict_status: str = ""


class _EmbeddingClient:
    """基于现有 OpenAIProvider 的 embedding 客户端，零额外依赖。"""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: int = 60) -> None:
        if not base_url or not api_key or not model:
            raise ValueError(
                f"MemoryEmbeddingIndex 配置不完整："
                f"base_url={'已配置' if base_url else '未配置'}, "
                f"api_key={'已配置' if api_key else '未配置'}, "
                f"model={'已配置' if model else '未配置'}"
            )
        try:
            from openai import OpenAI
            import httpx
        except ImportError as exc:
            raise ImportError(
                "MemoryEmbeddingIndex 需要 openai 和 httpx，"
                "请执行 `pip install openai httpx`。"
            ) from exc
        self._client = OpenAI(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            http_client=httpx.Client(timeout=timeout),
        )
        self._model = model

    def embed(self, text: str) -> Optional[List[float]]:
        try:
            resp = self._client.embeddings.create(
                model=self._model,
                input=text,
            )
            return resp.data[0].embedding
        except Exception as exc:
            logger.debug("embedding failed: %s", exc)
            return None


class MemoryEmbeddingIndex:
    """轻量语义索引：向量存在磁盘，不占内存。"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else memory_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.base_dir / "embeddings.json"
        self._client: Optional[_EmbeddingClient] = None
        self._model: str = ""
        self._vectors: Dict[str, List[float]] = {}
        self._lock = threading.RLock()
        self._load()

    def configure(self, base_url: str, api_key: str, model: str) -> None:
        with self._lock:
            self._client = _EmbeddingClient(base_url=base_url, api_key=api_key, model=model)
            self._model = model

    def _load(self) -> None:
        if not self._index_path.exists():
            return
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            with self._lock:
                self._vectors = {k: v for k, v in data.get("vectors", {}).items() if isinstance(v, list)}
        except Exception as exc:
            logger.debug("load memory index failed: %s", exc)
            self._vectors = {}

    def _save(self) -> None:
        with self._lock:
            try:
                self._index_path.write_text(
                    json.dumps({"vectors": self._vectors, "model": self._model}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as exc:
                logger.debug("memory index save failed: %s", exc)

    @staticmethod
    def _cosine(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def upsert(self, key: str, text: str) -> None:
        if not self._client:
            return
        vec = self._client.embed(text)
        if vec is not None:
            self._vectors[key] = vec
            self._save()

    def remove(self, key: str) -> None:
        self._vectors.pop(key, None)
        self._save()

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        if not self._client or not self._vectors:
            return []
        qvec = self._client.embed(query)
        if qvec is None:
            return []
        scored = [(k, self._cosine(qvec, v)) for k, v in self._vectors.items()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def clear(self) -> None:
        self._vectors.clear()
        self._save()


class PersistentMemory:
    """持久化记忆系统"""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = Path(base_dir) if base_dir is not None else memory_dir()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._index: Dict[str, Memory] = {}
        self._embedding_index = MemoryEmbeddingIndex(self.base_dir)
        # 记忆衰减：默认开启，半衰期 30 天，最低置信度 0.2
        self.decay_half_life_days: Optional[float] = 30.0
        self.decay_min_confidence: float = 0.2
        # 分类衰减：不同记忆类别有不同半衰期
        self.category_decay_rates: Dict[str, Optional[float]] = {
            "user_profile": 60.0,
            "user_preference": 45.0,
            "general": 30.0,
            "chat_history": 14.0,
            "skill": 45.0,
        }
        # 分类重要性：影响 recall / context / summary 排序
        self.category_importance: Dict[str, float] = {
            "user_profile": 1.5,
            "user_preference": 1.3,
            "general": 1.0,
            "chat_history": 0.8,
            "skill": 0.9,
        }
        self._decay_counter = 0
        self._decay_interval = 10
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        index_file = self.base_dir / "index.json"
        if not index_file.exists():
            return
        try:
            data = json.loads(index_file.read_text(encoding="utf-8"))
            with self._lock:
                self._index.clear()
                for item in data.get("memories", []):
                    memory = Memory(
                        key=item["key"],
                        value=item["value"],
                        category=item.get("category", "general"),
                        confidence=item.get("confidence", 1.0),
                        source=item.get("source", "user"),
                        created_at=item.get("created_at", ""),
                        updated_at=item.get("updated_at", ""),
                        embedding=item.get("embedding"),
                        embedding_model=item.get("embedding_model", ""),
                        access_count=int(item.get("access_count", 0)),
                        last_accessed_at=item.get("last_accessed_at", ""),
                        digest=item.get("digest", ""),
                    )
                    self._index[memory.key] = memory
                    if memory.embedding:
                        self._embedding_index._vectors[memory.key] = memory.embedding
        except Exception as exc:
            logger.warning("failed to load memory: %s", exc)

    def _save(self) -> None:
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
                    "embedding": m.embedding,
                    "embedding_model": m.embedding_model,
                    "access_count": m.access_count,
                    "last_accessed_at": m.last_accessed_at,
                    "digest": getattr(m, "digest", ""),
                }
                for m in self._index.values()
            ]
        }
        try:
            index_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.warning("failed to save memory: %s", exc)

    def _auto_consolidate(self, max_entries: int = 200) -> None:
        """当记忆条目过多时，压缩低置信条目并清理冗余。"""
        if len(self._index) <= max_entries:
            return
        # 先清理 duplicate digest（理论上 remember 已经拦截，这里做二次兜底）
        seen: Dict[str, str] = {}
        for key, m in list(self._index.items()):
            d = getattr(m, "digest", "") or ""
            if not d:
                continue
            if d in seen:
                del self._index[key]
                self._embedding_index.remove(key)
                continue
            seen[d] = key
        # 仍过多则按综合重要度丢弃最低的条目
        if len(self._index) > max_entries:
            # 最近 7 天内访问过的记忆优先保留，不参与淘汰
            recent_cutoff = datetime.now() - timedelta(days=7)
            recent_keys = {
                k for k, m in self._index.items()
                if m.last_accessed_at and datetime.fromisoformat(m.last_accessed_at) >= recent_cutoff
            }
            candidate_keys = [k for k in self._index.keys() if k not in recent_keys]
            candidate_keys.sort(key=lambda k: self._importance(self._index[k]))
            # 先把非近期记忆淘汰到 max_entries 以内
            excess = len(self._index) - max_entries
            for key in candidate_keys[:excess]:
                if key in self._index:
                    del self._index[key]
                    self._embedding_index.remove(key)
        if self._index:
            self._save()

    def compact(self, max_entries: int = 120) -> Dict[str, Any]:
        """
        主动整理记忆库：
        - 合并相似/重复条目
        - 压缩超长条目
        - 清理过期低置信条目
        返回整理结果。
        """
        with self._lock:
            before = len(self._index)
            merged = 0
            compressed = 0
            removed = 0
            # 先按 digest 合并重复
            by_digest: Dict[str, List[str]] = {}
            for key, m in list(self._index.items()):
                d = getattr(m, "digest", "") or key
                by_digest.setdefault(d, []).append(key)
            for keys in by_digest.values():
                if len(keys) <= 1:
                    continue
                    # 保留 access_count 最高的一条
                best = max(keys, key=lambda k: int(getattr(self._index[k], "access_count", 0) or 0))
                for k in keys:
                    if k == best:
                        continue
                    merged += 1
                    del self._index[k]
                    self._embedding_index.remove(k)
            # 压缩超长条目
            for m in self._index.values():
                v = getattr(m, "value", "") or ""
                if len(v) > 200:
                    m.value = v[:197].rstrip() + "..."
                    m.updated_at = _now_iso()
                    compressed += 1
            # 清理过期低置信条目
            cutoff = datetime.now() - timedelta(days=30)
            for key, m in list(self._index.items()):
                conf = getattr(m, "confidence", 1.0) or 1.0
                last = getattr(m, "last_accessed_at", "") or getattr(m, "updated_at", "") or getattr(m, "created_at", "") or ""
                try:
                    last_dt = datetime.fromisoformat(last)
                except Exception:
                    last_dt = None
                if last_dt is not None and last_dt < cutoff and conf < 0.3:
                    del self._index[key]
                    self._embedding_index.remove(key)
                    removed += 1
            if self._index:
                self._save()
            return {
                "before": before,
                "after": len(self._index),
                "merged": merged,
                "compressed": compressed,
                "removed": removed,
            }

    def configure_embeddings(self, base_url: str, api_key: str, model: str) -> None:
        """启用语义检索。未调用时退化为纯字符串匹配。"""
        self._embedding_index.configure(base_url, api_key, model)

    def _resolve_conflict(self, new_key: str, new_value: str, category: str) -> None:
        """按 category 检查是否已存在相反/矛盾记忆，若存在则更新为新值并标记 supersedes。"""
        neg_patterns = ['不喜欢', '讨厌', '反感', '别叫', '不要', '不是', '不会', '不']
        is_neg = any(p in new_value for p in neg_patterns)
        for key, m in list(self._index.items()):
            if m.category != category or key == new_key:
                continue
            if getattr(m, "conflict_status", "") == "superseded":
                continue
            val = m.value
            pos_match = any(p in val for p in ['喜欢', '爱', '常', '经常', '是'])
            neg_match = any(p in val for p in neg_patterns)
            if is_neg and pos_match:
                m.conflict_status = "superseded"
                m.supersedes_key = new_key
                m.confidence = max(0.1, m.confidence - 0.3)
                m.updated_at = _now_iso()
                logger.debug("memory conflict resolved: %s superseded by %s", key, new_key)
                return
            if not is_neg and neg_match:
                m.conflict_status = "superseded"
                m.supersedes_key = new_key
                m.confidence = max(0.1, m.confidence - 0.3)
                m.updated_at = _now_iso()
                logger.debug("memory conflict resolved: %s superseded by %s", key, new_key)
                return

    def remember(
        self,
        key: str,
        value: str,
        category: str = "general",
        confidence: float = 1.0,
        source: str = "user",
    ) -> None:
        now = _now_iso()
        with self._lock:
            # 防重复：相同 category 下若已有 digest 相似条目，则只更新 access_count
            if key not in self._index:
                candidate_digest = _short(f"{category}:{value}", limit=64)
                for m in self._index.values():
                    if m.category == category and getattr(m, "digest", "") and m.digest == candidate_digest:
                        m.access_count = int(m.access_count) + 1
                        m.last_accessed_at = now
                        self._embedding_index.upsert(m.key, f"{m.key}: {m.value}")
                        self._save()
                        logger.debug("memory duplicate skipped: %s", key)
                        return

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
                    access_count=0,
                    last_accessed_at="",
                    digest=_short(f"{category}:{value}", limit=64),
                )
                self._resolve_conflict(key, value, category)
            memory.access_count = int(memory.access_count) + 1
            memory.last_accessed_at = now
            self._index[key] = memory
            self._embedding_index.upsert(key, f"{key}: {value}")
            self._save()
            logger.debug("memory stored: %s", key)
            # 自动提炼：条目数过多时做压缩
            self._auto_consolidate()

    def recall(self, key: str) -> Optional[str]:
        with self._lock:
            memory = self._index.get(key)
            if memory:
                memory.access_count = int(memory.access_count) + 1
                memory.last_accessed_at = _now_iso()
                # 被多次 recall 的记忆，confidence 缓慢回升，上限 1.0
                if memory.confidence < 1.0:
                    memory.confidence = min(1.0, memory.confidence + 0.05)
                    memory.updated_at = _now_iso()
                return memory.value
        return None

    def forget(self, key: str) -> bool:
        with self._lock:
            if key in self._index:
                del self._index[key]
                self._embedding_index.remove(key)
                self._save()
                return True
        return False

    def _apply_decay(self) -> None:
        """按时间衰减调整 confidence，基于 last_accessed_at；支持分类半衰期。"""
        if self.decay_half_life_days is None:
            return
        now = datetime.now()
        for memory in self._index.values():
            if memory.confidence <= self.decay_min_confidence:
                continue
            last = memory.last_accessed_at or memory.updated_at or memory.created_at
            if not last:
                continue
            try:
                last_dt = datetime.fromisoformat(last)
                days = max((now - last_dt).total_seconds() / 86400.0, 0.0)
            except Exception:
                continue
            if days <= 0:
                continue
            half_life = self.category_decay_rates.get(memory.category, self.decay_half_life_days)
            if half_life is None or half_life <= 0:
                continue
            decay = 2 ** (-days / float(half_life))
            memory.confidence = max(self.decay_min_confidence, memory.confidence * decay)
            if memory.confidence < 1.0:
                memory.updated_at = now.isoformat()

    def _maybe_decay(self) -> None:
        """每 N 次 search 做一次衰减，减少运行时开销。"""
        with self._lock:
            self._decay_counter += 1
            if self._decay_counter >= self._decay_interval:
                self._decay_counter = 0
                self._apply_decay()

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[Memory]:
        with self._lock:
            self._maybe_decay()
            query_lower = query.lower()
            # 简单同义词/归一化：常见称呼、语气词、代词
            norm_map = {
                '贾总': ['贾总', 'boss', '老板', '老大'],
                '你': ['你', '您', 'prism', '助手', 'agent'],
                '我': ['我', '本人', '本人', '鄙人'],
            }
            synonyms: List[str] = []
            for base, alts in norm_map.items():
                if base in query_lower:
                    synonyms.extend(alts)
            synonyms = list(set(synonyms))

            candidates: List[Memory] = []
            seen_keys = set()
            for memory in self._index.values():
                if category and memory.category != category:
                    continue
                key_lower = memory.key.lower()
                val_lower = memory.value.lower()
                if query_lower in key_lower or query_lower in val_lower:
                    candidates.append(memory)
                    seen_keys.add(memory.key)
                elif synonyms:
                    if any(s in key_lower or s in val_lower for s in synonyms):
                        candidates.append(memory)
                        seen_keys.add(memory.key)

            semantic_hits = self._embedding_index.search(query, top_k=max(limit, 10))
            for key, _ in semantic_hits:
                if key in seen_keys:
                    continue
                memory = self._index.get(key)
                if memory and (category is None or memory.category == category):
                    candidates.append(memory)
                    seen_keys.add(key)

            for memory in self._index.values():
                if memory.key in seen_keys:
                    continue
                if category and memory.category != category:
                    continue
                candidates.append(memory)

            now = datetime.now()
            candidates.sort(key=lambda m: self._importance(m, now=now), reverse=True)
            return candidates[:limit]

    def _importance(self, memory: Memory, now: Optional[datetime] = None) -> float:
        """综合重要度：confidence + access_count 加成 + 分类加成 + 访问时间加成。"""
        if now is None:
            now = datetime.now()
        score = float(memory.confidence)
        score *= float(self.category_importance.get(memory.category, 1.0))
        score += min(float(memory.access_count) * 0.05, 0.5)
        try:
            last = memory.last_accessed_at or memory.updated_at or memory.created_at
            if last:
                last_dt = datetime.fromisoformat(last)
                hours = max((now - last_dt).total_seconds() / 3600.0, 0.0)
                if hours < 24:
                    score += 0.3
                elif hours < 168:
                    score += 0.15
        except Exception:
            pass
        return score

    def summarize(self, category: Optional[str] = None, max_chars: int = 800) -> str:
        """简单记忆摘要：按综合重要度取 top 条目拼成文本。"""
        memories = sorted(self._index.values(), key=lambda m: self._importance(m), reverse=True)
        if category:
            memories = [m for m in memories if m.category == category]
        if not memories:
            return ""
        lines = ["## 记忆摘要"]
        current_len = len(lines[0])
        for m in memories[:50]:
            text = f"- [{m.category}] {m.key}: {m.value}"
            if current_len + len(text) + 1 > max_chars:
                break
            lines.append(text)
            current_len += len(text) + 1
        return "\n".join(lines)

    def list_by_category(self, category: str) -> List[Memory]:
        return [m for m in self._index.values() if m.category == category]

    def get_context(self, max_items: int = 5, budget_chars: int = 1500, scope: str = "default") -> str:
        """
        生成记忆上下文块，并尽量控制在 budget_chars 以内。
        结构: 【身份】→【相关(query命中)】→【兜底(按重要度)】
        """
        scope_chat_prefix = f"chat_history:{scope}"
        # 身份类记忆全局加载
        identities = [m for m in self._index.values() if m.category == "user_profile"]
        # 按 scope 过滤对话记忆，避免不同 persona 串扰
        rest = [m for m in self._index.values() if m.category != "user_profile" and (m.category == scope_chat_prefix or m.category == "chat_history")]
        rest.sort(key=lambda m: self._importance(m), reverse=True)
        chat = rest[:2]
        non_chat = [m for m in self._index.values() if m.category not in ("user_profile", "chat_history", scope_chat_prefix)]

        # 先放身份，再放 chat_history，再按重要度取非chat记忆
        picked = identities + chat
        remaining_budget = budget_chars
        for m in picked:
            remaining_budget -= len(f"- {m.key}: {m.value}\n")
        # 从非chat记忆中按重要度挑，不超出剩余预算
        for m in non_chat:
            if len(picked) >= max_items:
                break
            val = m.value
            if len(val) > 120:
                val = val[:117] + "..."
            cost = len(f"- [{m.category}] {m.key}: {val}\n")
            if cost > remaining_budget:
                # 尝试只保留更短摘要
                short_val = val[:60].rstrip() + "..." if len(val) > 60 else val
                short_cost = len(f"- [{m.category}] {m.key}: {short_val}\n")
                if short_cost <= remaining_budget:
                    val = short_val
                else:
                    continue
            picked.append(m)
            remaining_budget -= cost

        if not picked:
            return ""
        lines = ["## 记忆上下文"]
        if identities:
            lines.append("【身份】")
            for m in identities[:3]:
                lines.append(f"- {m.key}: {m.value}")
        for m in picked[len(identities):]:
            if m.category in ("chat_history", scope_chat_prefix):
                lines.append(f"- {m.value}")
            else:
                val = m.value
                if len(val) > 120:
                    val = val[:117] + "..."
                lines.append(f"- [{m.category}] {m.key}: {val}")
        return "\n".join(lines)

    def clear(self) -> None:
        self._index.clear()
        self._embedding_index.clear()
        self._save()


# 全局记忆实例
memory = PersistentMemory()
persistent_memory = memory
