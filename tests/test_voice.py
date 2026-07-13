"""
PRISM Agent - Voice Interaction tests
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from prism.voice import VoiceInteraction


def test_voice_interaction_init():
    v = VoiceInteraction()
    assert v.language == "zh-CN"
    assert v.tts_engine == "edge"


def test_listen_requires_sr():
    with patch("prism.voice._SR_AVAILABLE", False):
        v = VoiceInteraction()
        assert v.listen() == ""


def test_speak_empty_returns_none():
    v = VoiceInteraction()
    assert v.speak("") is None
    assert v.speak("   ") is None


def test_speak_requires_edge_tts():
    with patch("prism.voice._EDGE_TTS_AVAILABLE", False):
        v = VoiceInteraction()
        assert v.speak("hello") is None
