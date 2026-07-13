"""
PRISM Agent - RAG tests
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from prism.rag import LocalRAG, _chunk_text


def test_chunk_text_splits_long_text():
    text = "a" * 1200
    chunks = _chunk_text(text, chunk_size=600, overlap=120)
    assert len(chunks) >= 2
    assert all(0 < len(c) <= 600 for c in chunks)


def test_local_rag_build_index(tmp_path):
    root = tmp_path / "novel"
    root.mkdir()
    (root / "ch1.md").write_text("第一章内容", encoding="utf-8")
    (root / "ch2.md").write_text("第二章内容", encoding="utf-8")
    rag = LocalRAG(str(root), chunk_size=20, overlap=0)
    res = rag.build()
    assert res["success"] is True
    assert res["files"] == 2
    assert res["chunks"] >= 2
    assert (root / ".prism_rag_index.json").exists()


def test_local_rag_query_empty():
    rag = LocalRAG()
    assert rag.query("") == []
    assert rag.query_keyword("") == []


def test_local_rag_query_keyword(tmp_path):
    root = tmp_path / "novel"
    root.mkdir()
    (root / "ch1.md").write_text("保安铁锤第一章", encoding="utf-8")
    rag = LocalRAG(str(root), chunk_size=20, overlap=0)
    rag.build()
    out = rag.query_keyword("保安铁锤")
    assert len(out) >= 1
    assert "保安铁锤" in out[0]["text"]
