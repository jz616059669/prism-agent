"""
PRISM Agent - 多模态测试
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from prism.multimodal import multimodal, MultimodalEngine, VisionEngine, AudioEngine, _CapabilityDetector


def test_multimodal_capabilities_keys():
    caps = multimodal.capabilities()
    assert "vision" in caps
    assert "audio" in caps
    assert isinstance(caps["vision"], dict)
    assert isinstance(caps["audio"], dict)


def test_describe_image_missing_file():
    result = multimodal.describe_image("__nonexistent__.png")
    assert result["success"] is False
    assert "文件不存在" in result["error"]


def test_image_to_base64_missing_file():
    data = multimodal.image_to_base64("__nonexistent__.png")
    assert data is None


def test_transcribe_audio_missing_file():
    result = multimodal.transcribe_audio("__nonexistent__.mp3")
    assert result["success"] is False
    assert "文件不存在" in result["error"]


def test_text_to_speech_empty_text():
    result = multimodal.text_to_speech("")
    assert result["success"] is False
    assert "为空" in result["error"]
