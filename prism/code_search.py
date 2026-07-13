"""
PRISM Agent - 代码语义搜索
基于 AST + 简单 TF-IDF 的跨文件代码检索
"""

from __future__ import annotations

import ast
import logging
import math
import os
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CodeChunk:
    path: str
    name: str = ""
    kind: str = "module"
    code: str = ""
    tokens: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "kind": self.kind,
            "code": self.code,
            "tokens": self.tokens,
        }


class CodeSearchEngine:
    def __init__(self, roots: Optional[List[str]] = None) -> None:
        self.roots = [Path(r) for r in (roots or [os.getcwd()]) if r]
        self._chunks: List[CodeChunk] = []
        self._df: Counter = Counter()
        self._n = 0
        self._ready = False

    def index(self, max_files: int = 500) -> int:
        self._chunks = []
        self._df = Counter()
        files: List[Path] = []
        for root in self.roots:
            if not root.exists():
                continue
            for dirpath, _, filenames in os.walk(str(root)):
                for fn in filenames:
                    if fn.endswith(".py"):
                        files.append(Path(dirpath) / fn)
                        if len(files) >= max_files:
                            break
                if len(files) >= max_files:
                    break
            if len(files) >= max_files:
                break
        for path in files:
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
                chunks = self._chunk(path, text)
                self._chunks.extend(chunks)
                for chunk in chunks:
                    for token in set(chunk.tokens):
                        self._df[token] += 1
            except Exception:
                continue
        self._n = len(self._chunks)
        self._ready = True
        return self._n

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self._ready or not self._chunks:
            return []
        query_tokens = self._tokenize(query)
        scores: List[tuple[float, CodeChunk]] = []
        for chunk in self._chunks:
            score = self._score(query_tokens, chunk)
            scores.append((score, chunk))
        scores.sort(key=lambda x: x[0], reverse=True)
        return [c.to_dict() for _, c in scores[:top_k] if _ > 0]

    def _chunk(self, path: Path, text: str) -> List[CodeChunk]:
        chunks: List[CodeChunk] = []
        try:
            tree = ast.parse(text)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    chunks.append(CodeChunk(
                        path=str(path),
                        name=node.name,
                        kind="function",
                        code=text[node.lineno - 1: node.end_lineno],
                        tokens=self._tokenize(ast.unparse(node)),
                    ))
                elif isinstance(node, ast.ClassDef):
                    chunks.append(CodeChunk(
                        path=str(path),
                        name=node.name,
                        kind="class",
                        code=text[node.lineno - 1: node.end_lineno],
                        tokens=self._tokenize(ast.unparse(node)),
                    ))
        except Exception:
            pass
        if not chunks:
            chunks.append(CodeChunk(path=str(path), kind="module", code=text[:1000], tokens=self._tokenize(text)))
        return chunks

    def _tokenize(self, text: str) -> List[str]:
        tokens = []
        for line in (text or "").splitlines():
            line = line.strip()
            if line.startswith("#") or line.startswith("import ") or line.startswith("from "):
                continue
            for word in line.split():
                word = "".join(ch for ch in word if ch.isalnum())
                if word:
                    tokens.append(word.lower())
        return tokens

    def _score(self, query_tokens: List[str], chunk: CodeChunk) -> float:
        if not query_tokens or not chunk.tokens:
            return 0.0
        tf = Counter(chunk.tokens)
        score = 0.0
        for token in query_tokens:
            if token in tf:
                tf_val = 1 + math.log(tf[token])
                idf_val = math.log((self._n + 1) / (self._df.get(token, 0) + 1)) + 1
                score += tf_val * idf_val
        return score


code_search = CodeSearchEngine()
