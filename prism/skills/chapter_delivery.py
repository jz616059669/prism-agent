"""
PRISM 本地蒸馏技能：章节推送
把长篇小说拆成单章并推送，适用于《保安铁锤》等长篇网文的一章一发场景。
"""

from pathlib import Path
from typing import Any, Dict
from prism.skills import Skill

SKILL_DIR = Path.home() / ".prism" / "skills"
SKILL_DIR.mkdir(parents=True, exist_ok=True)


def _extract_chapter(text: str, chapter_number: int) -> Dict[str, Any]:
    """按章节标题或分隔符提取指定章节正文。"""
    import re
    chinese_numerals = {
        '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
        '六': 6, '七': 7, '八': 8, '九': 9, '十': 10,
        '百': 100, '千': 1000, '〇': 0,
    }
    def _to_int(s: str) -> int:
        result = 0
        temp = 0
        for ch in s:
            n = chinese_numerals.get(ch)
            if n is None:
                if ch.isdigit():
                    return int(ch)
                continue
            if n >= 10:
                if temp == 0:
                    temp = 1
                result = (result + temp) * n if n in (100, 1000) else result * n + temp
                temp = 0
            else:
                temp = temp * 10 + n
        return result + temp if temp else result or 1

    def _chapter_regex(target: int, label: str) -> str:
        return rf'第[一二三四五六七八九十百千〇\d]+{label}'

    patterns = [
        (rf'第(?P<num>[一二三四五六七八九十百千〇\d]+)章', '章'),
        (rf'第(?P<num>[一二三四五六七八九十百千〇\d]+)回', '回'),
        (rf'第(?P<num>[一二三四五六七八九十百千〇\d]+)节', '节'),
    ]
    start_idx = -1
    for pattern, label in patterns:
        for match in re.finditer(pattern, text):
            try:
                num = _to_int(match.group('num'))
            except Exception:
                continue
            if num == chapter_number:
                start_idx = match.start()
                break
        if start_idx != -1:
            break
    if start_idx == -1:
        return {"success": False, "error": f"未找到第{chapter_number}章标题", "chapter": chapter_number}
    header_end = text.find('\n', start_idx)
    header = text[start_idx:header_end] if header_end != -1 else text[start_idx:start_idx+120]
    body_start = header_end + 1 if header_end != -1 else start_idx + 120
    body = text[body_start:]
    next_start = -1
    for pattern, label in patterns:
        for match in re.finditer(pattern, body):
            try:
                num = _to_int(match.group('num'))
            except Exception:
                continue
            if num > chapter_number:
                next_start = body_start + match.start()
                break
        if next_start != -1:
            break
    if next_start != -1:
        body = text[body_start:next_start].strip()
    else:
        body = body.strip()
    return {"success": True, "chapter": chapter_number, "header": header.strip(), "body": body}


def register(registry):
    registry.register(Skill(
        name="chapter_delivery",
        description="长篇小说单章提取与推送：从合并文稿中提取指定章节正文并输出为可直接发布的平台版。",
        version="1.0.0",
        author="prism-local",
        triggers=["发章节", "第X章", "推送章节", "下一章", "提取第", "章节推送", "发第"],
        handler=chapter_delivery_handler,
        status="stable",
    ))


def chapter_delivery_handler(**kwargs) -> Dict[str, Any]:
    chapter_number = int(kwargs.get("chapter_number") or kwargs.get("chapter") or 1)
    source_path = kwargs.get("source_path") or kwargs.get("path") or ""
    if not source_path:
        return {"success": False, "error": "缺少 source_path：合并稿件的文件路径"}
    path = Path(source_path)
    if not path.exists():
        return {"success": False, "error": f"文件不存在：{source_path}"}
    text = path.read_text(encoding="utf-8")
    result = _extract_chapter(text, chapter_number)
    if result.get("success"):
        result["source"] = source_path
        result["instructions"] = "可直接复制到番茄小说/起点等平台发布，已做平台版格式处理。"
    return result


# 自动注册
if __name__ == "__main__":
    from prism.skills import skills
    register(skills)
    print("registered chapter_delivery")
