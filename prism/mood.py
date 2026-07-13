"""
PRISM Agent - 情绪识别 + 自适应回复
分析用户输入情感，动态调整语气/长度
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Mood(str, Enum):
    neutral = "neutral"
    positive = "positive"
    negative = "negative"
    urgent = "urgent"
    sad = "sad"
    angry = "angry"


@dataclass
class MoodResult:
    mood: Mood = Mood.neutral
    score: float = 0.0
    cues: List[str] = field(default_factory=list)
    adaption: Dict[str, Any] = field(default_factory=dict)


_POSITIVE_CUES = ["谢谢", "感谢", "太棒了", "不错", "很好", "厉害", "牛", "666", "good", "great", "thanks", "love"]
_NEGATIVE_CUES = ["垃圾", "废物", "崩", "错", "失败", "慢", "投诉", "shit", "fuck", "bad", "terrible", "hate"]
_URGENT_CUES = ["紧急", "马上", "立刻", "快点", "快", "急", "now", "urgent", "asap"]
_SAD_CUES = ["难过", "失落", "心酸", "想哭", "难受", "sad", "depressed", "cry"]
_ANGRY_CUES = ["滚", "别烦", "闭嘴", "混蛋", "fuck", "stupid", "idiot", "垃圾", "废物"]


def detect_mood(text: str) -> MoodResult:
    t = (text or "").lower()
    result = MoodResult(cues=[])
    for token in _POSITIVE_CUES:
        if token in t:
            result.cues.append(token)
            result.mood = Mood.positive
            result.score += 0.3
    for token in _NEGATIVE_CUES:
        if token in t:
            result.cues.append(token)
            result.mood = Mood.negative
            result.score -= 0.3
    for token in _URGENT_CUES:
        if token in t:
            result.cues.append(token)
            result.mood = Mood.urgent
            result.score += 0.5
    for token in _SAD_CUES:
        if token in t:
            result.cues.append(token)
            result.mood = Mood.sad
            result.score -= 0.2
    for token in _ANGRY_CUES:
        if token in t:
            result.cues.append(token)
            result.mood = Mood.angry
            result.score -= 0.6
    result.score = max(-1.0, min(1.0, result.score))
    result = _apply_adaption(result)
    return result


def _apply_adaption(result: MoodResult) -> MoodResult:
    if result.mood == Mood.urgent:
        result.adaption = {"style": "concise", "length": "short", "prefix": "⚡ 紧急处理："}
    elif result.mood == Mood.angry:
        result.adaption = {"style": "calm", "length": "medium", "prefix": "收到，我来冷静处理："}
    elif result.mood == Mood.sad:
        result.adaption = {"style": "empathetic", "length": "medium", "prefix": "我理解你的感受："}
    elif result.mood == Mood.positive:
        result.adaption = {"style": "energetic", "length": "medium", "prefix": "👍 好的！"}
    elif result.mood == Mood.negative:
        result.adaption = {"style": "neutral", "length": "short", "prefix": "收到，我来排查："}
    else:
        result.adaption = {"style": "neutral", "length": "normal", "prefix": ""}
    return result
