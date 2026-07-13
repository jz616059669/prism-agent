"""
PRISM Agent - Context References（@引用）
在用户消息中检测 @文件/@文件夹/@URL，自动 inline 展开内容。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional

try:
    import requests
except Exception:
    requests = None  # type: ignore[assignment]


_REF_RE = re.compile(r"@([^\s]+)")


def _read_file(path_str: str, max_chars: int = 12000) -> str:
    try:
        p = Path(path_str)
        if not p.exists():
            return f"[引用缺失: {path_str}]"
        if p.is_file():
            text = p.read_text(encoding="utf-8", errors="replace")
            if len(text) > max_chars:
                text = text[:max_chars] + f"\n...[截断，共 {len(text)} 字符]"
            return f"[文件: {path_str}]\n{text}"
        if p.is_dir():
            entries = []
            for child in sorted(p.iterdir()):
                entries.append(child.name + ("/" if child.is_dir() else ""))
            listing = "\n".join(entries[:200])
            return f"[目录: {path_str}]\n{listing}"
        return f"[引用未知类型: {path_str}]"
    except Exception as exc:
        return f"[引用失败: {path_str} -> {exc}]"


def _fetch_url(url: str, max_chars: int = 8000) -> str:
    if requests is None:
        return "[引用失败: requests 未安装]"
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "PRISM-Agent/2.0"})
        resp.raise_for_status()
        text = resp.text
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n...[截断，共 {len(text)} 字符]"
        return f"[URL: {url}]\n{text}"
    except Exception as exc:
        return f"[引用失败: {url} -> {exc}]"


def expand_references(user_message: str, cwd: Optional[str] = None) -> str:
    """
    将 @path / @URL 展开为内联内容。
    默认相对 cwd 解析文件路径；URL 直接请求。
    """
    if not user_message or "@" not in user_message:
        return user_message
    base = Path(cwd) if cwd else Path(os.getcwd())
    parts = _REF_RE.split(user_message)
    # split 结果: [prefix, ref1, middle, ref2, suffix, ...]
    out = parts[0]
    i = 1
    while i < len(parts) - 1:
        ref = parts[i]
        middle = parts[i + 1] if i + 1 < len(parts) else ""
        expanded = _resolve_ref(ref, base)
        out += expanded + middle
        i += 2
    return out


def _resolve_ref(ref: str, base: Path) -> str:
    ref = ref.strip()
    if not ref:
        return "@"
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", ref):
        return _fetch_url(ref)
    p = (base / ref).expanduser().resolve()
    return _read_file(str(p))


__all__ = ["expand_references"]
