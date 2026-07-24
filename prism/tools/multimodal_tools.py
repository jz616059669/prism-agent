"""
PRISM Agent - 多模态工具
封装本地视觉/语音能力为可调用工具。
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from prism.interfaces import Tool
from prism.multimodal import multimodal

logger = logging.getLogger("prism.tools.multimodal")


class VisionDescribeTool(Tool):
    """描述图片内容（本地 OCR / 元数据提取）"""

    name = "vision_describe"
    description = "描述图片内容，支持 OCR 提取文字。参数: image_path (必填), prompt (可选)"
    input_schema = {
        "type": "object",
        "properties": {
            "image_path": {"type": "string", "description": "图片路径"},
            "prompt": {"type": "string", "description": "描述提示词", "default": "描述这张图片的内容"},
        },
        "required": ["image_path"],
    }

    def execute(self, image_path: str, prompt: str = "描述这张图片的内容") -> Dict[str, Any]:
        if not image_path:
            return {"success": False, "error": "image_path is required"}
        return multimodal.describe_image(image_path, prompt)


class ImageToBase64Tool(Tool):
    """将图片转为 base64 data URI（供外部 API 使用）"""

    name = "image_to_base64"
    description = "将图片转为 base64 data URI。参数: image_path (必填)"
    input_schema = {
        "type": "object",
        "properties": {
            "image_path": {"type": "string", "description": "图片路径"},
        },
        "required": ["image_path"],
    }

    def execute(self, image_path: str) -> Dict[str, Any]:
        if not image_path:
            return {"success": False, "error": "image_path is required"}
        data = multimodal.image_to_base64(image_path)
        if data is None:
            return {"success": False, "error": f"file not found: {image_path}"}
        return {"success": True, "content": data, "metadata": {"size": len(data)}}


class AudioTranscribeTool(Tool):
    """语音转文字（本地 whisper / 占位）"""

    name = "audio_transcribe"
    description = "将音频转为文字。参数: audio_path (必填), language (可选，默认 zh)"
    input_schema = {
        "type": "object",
        "properties": {
            "audio_path": {"type": "string", "description": "音频文件路径"},
            "language": {"type": "string", "description": "语言代码", "default": "zh"},
        },
        "required": ["audio_path"],
    }

    def execute(self, audio_path: str, language: str = "zh") -> Dict[str, Any]:
        if not audio_path:
            return {"success": False, "error": "audio_path is required"}
        return multimodal.transcribe_audio(audio_path, language)


class TextToSpeechTool(Tool):
    """文字转语音（本地 edge-tts / 占位）"""

    name = "text_to_speech"
    description = "将文字转为语音文件。参数: text (必填), output_path (可选), voice (可选)"
    input_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "要转换的文字"},
            "output_path": {"type": "string", "description": "输出音频路径", "default": ""},
            "voice": {"type": "string", "description": "音色", "default": "zh-CN-XiaoxiaoNeural"},
        },
        "required": ["text"],
    }

    def execute(self, text: str, output_path: str = "", voice: str = "zh-CN-XiaoxiaoNeural") -> Dict[str, Any]:
        if not text or not text.strip():
            return {"success": False, "error": "text is required"}
        return multimodal.text_to_speech(text, output_path or None, voice)
