"""
PRISM Agent - 本地多模态能力
支持：视觉理解（图片描述/OCR）、语音转文字、文字转语音
零额外依赖：优先使用系统自带工具；可选接入本地模型。
"""
from __future__ import annotations

import base64
import json
import logging
import mimetypes
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("prism.multimodal")


@dataclass
class MultimodalResult:
    """多模态处理结果"""
    success: bool
    content: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = None  # type: ignore

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "metadata": self.metadata,
        }


class _CapabilityDetector:
    """检测本机可用多模态能力（零依赖优先）"""

    @staticmethod
    def check_ffmpeg() -> bool:
        return shutil.which("ffmpeg") is not None

    @staticmethod
    def check_tesseract() -> bool:
        return shutil.which("tesseract") is not None

    @staticmethod
    def check_pil() -> bool:
        try:
            from PIL import Image  # noqa: F401
            return True
        except ImportError:
            return False

    @staticmethod
    def check_whisper() -> bool:
        return shutil.which("whisper") is not None

    @staticmethod
    def check_edge_tts() -> bool:
        return shutil.which("edge-tts") is not None

    @staticmethod
    def get_vision_capabilities() -> Dict[str, bool]:
        return {
            "ffmpeg": _CapabilityDetector.check_ffmpeg(),
            "tesseract": _CapabilityDetector.check_tesseract(),
            "pillow": _CapabilityDetector.check_pil(),
        }

    @staticmethod
    def get_audio_capabilities() -> Dict[str, bool]:
        return {
            "ffmpeg": _CapabilityDetector.check_ffmpeg(),
            "whisper": _CapabilityDetector.check_whisper(),
            "edge_tts": _CapabilityDetector.check_edge_tts(),
        }


class VisionEngine:
    """视觉理解引擎：图片描述、OCR、内容提取"""

    def __init__(self) -> None:
        self._caps = _CapabilityDetector.get_vision_capabilities()

    def describe(self, image_path: str, prompt: str = "描述这张图片的内容") -> MultimodalResult:
        """描述图片内容；优先本地 OCR，无依赖时返回占位结果"""
        path = Path(image_path)
        if not path.exists():
            return MultimodalResult(success=False, error=f"文件不存在: {image_path}")

        if not self._caps.get("pillow"):
            return MultimodalResult(
                success=True,
                content=f"[图片: {path.name}] 本地未安装 Pillow，无法提取元数据。",
                metadata={"hint": "pip install pillow"},
            )

        try:
            from PIL import Image as PILImage
            with PILImage.open(path) as img:
                meta = {
                    "format": img.format,
                    "mode": img.mode,
                    "size": list(img.size),
                }
                # 如果无 tesseract，至少返回元数据
                if not self._caps.get("tesseract"):
                    return MultimodalResult(
                        success=True,
                        content=f"[图片: {path.name}] 尺寸 {meta['size'][0]}x{meta['size'][1]}，"
                                f"格式 {meta['format']}。本地未安装 Tesseract OCR，无法提取文字。",
                        metadata=meta,
                    )

                # 使用 tesseract OCR
                return self._ocr_with_tesseract(path, prompt, meta)
        except Exception as exc:
            logger.debug("vision describe failed: %s", exc)
            return MultimodalResult(success=False, error=f"图片处理失败: {exc}")

    def _ocr_with_tesseract(self, path: Path, prompt: str, meta: Dict[str, Any]) -> MultimodalResult:
        """Tesseract OCR 提取"""
        try:
            result = subprocess.run(
                ["tesseract", str(path), "stdout", "--lang", "chi_sim+eng"],
                capture_output=True, text=True, timeout=30, check=False
            )
            text = result.stdout.strip()
            if text:
                return MultimodalResult(
                    success=True,
                    content=f"[图片 OCR 结果]\n{text}",
                    metadata=meta,
                )
            return MultimodalResult(
                success=True,
                content=f"[图片: {path.name}] 未检测到文字内容。",
                metadata=meta,
            )
        except Exception as exc:
            return MultimodalResult(success=False, error=f"OCR 失败: {exc}")

    def to_base64(self, image_path: str) -> Optional[str]:
        """将图片转为 base64 data URI（供外部 API 使用）"""
        path = Path(image_path)
        if not path.exists():
            return None
        try:
            data = path.read_bytes()
            mime = mimetypes.guess_type(str(path))[0] or "image/png"
            return f"data:{mime};base64,{base64.b64encode(data).decode('utf-8')}"
        except Exception:
            return None


class AudioEngine:
    """语音引擎：ASR（语音转文字）+ TTS（文字转语音）"""

    def __init__(self) -> None:
        self._caps = _CapabilityDetector.get_audio_capabilities()
        self._tmp_dir = Path(tempfile.gettempdir()) / "prism_multimodal"
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

    def transcribe(self, audio_path: str, language: str = "zh") -> MultimodalResult:
        """语音转文字；优先 whisper，回退 ffmpeg + 占位"""
        path = Path(audio_path)
        if not path.exists():
            return MultimodalResult(success=False, error=f"文件不存在: {audio_path}")

        if self._caps.get("whisper"):
            return self._transcribe_with_whisper(path, language)

        if self._caps.get("ffmpeg"):
            return MultimodalResult(
                success=True,
                content=f"[音频: {path.name}] 本地已安装 ffmpeg，但未安装 whisper。"
                        f"安装 whisper 后可启用语音转文字。",
                metadata={"hint": "pip install openai-whisper", "file": str(path)},
            )

        return MultimodalResult(
            success=False,
            error="未检测到 whisper 或 ffmpeg，无法转录音频。",
            metadata={"hint": "pip install openai-whisper"},
        )

    def _transcribe_with_whisper(self, path: Path, language: str) -> MultimodalResult:
        """使用 whisper CLI 转录音频"""
        try:
            output_dir = self._tmp_dir / f"whisper_{path.stem}"
            output_dir.mkdir(exist_ok=True)
            result = subprocess.run(
                [
                    "whisper",
                    str(path),
                    "--model", "base",
                    "--language", language,
                    "--output_dir", str(output_dir),
                    "--output_format", "txt",
                ],
                capture_output=True, text=True, timeout=120, check=False
            )
            if result.returncode != 0:
                return MultimodalResult(success=False, error=f"whisper 失败: {result.stderr}")

            txt_file = output_dir / f"{path.stem}.txt"
            if txt_file.exists():
                text = txt_file.read_text(encoding="utf-8").strip()
                return MultimodalResult(
                    success=True,
                    content=text,
                    metadata={"file": str(path), "engine": "whisper"},
                )
            return MultimodalResult(success=True, content="[whisper] 未生成文本输出。")
        except Exception as exc:
            return MultimodalResult(success=False, error=f"转录失败: {exc}")

    def speak(self, text: str, output_path: Optional[str] = None, voice: str = "zh-CN-XiaoxiaoNeural") -> MultimodalResult:
        """文字转语音；优先 edge-tts，无依赖时返回占位"""
        if not text or not text.strip():
            return MultimodalResult(success=False, error="文本为空")

        if self._caps.get("edge_tts"):
            return self._speak_with_edge_tts(text, output_path, voice)

        return MultimodalResult(
            success=True,
            content=f"[TTS] 本地未安装 edge-tts，无法将文字转为语音。",
            metadata={"hint": "pip install edge-tts", "text": text[:100]},
        )

    def _speak_with_edge_tts(self, text: str, output_path: Optional[str], voice: str) -> MultimodalResult:
        """使用 edge-tts 生成语音"""
        try:
            out = Path(output_path) if output_path else self._tmp_dir / f"tts_{hash(text)}.mp3"
            out.parent.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(
                [
                    "edge-tts",
                    "--text", text,
                    "--voice", voice,
                    "--write-media", str(out),
                ],
                capture_output=True, text=True, timeout=60, check=False
            )
            if result.returncode != 0:
                return MultimodalResult(success=False, error=f"edge-tts 失败: {result.stderr}")
            return MultimodalResult(
                success=True,
                content=f"[TTS] 语音已生成: {out}",
                metadata={"file": str(out), "engine": "edge-tts", "voice": voice},
            )
        except Exception as exc:
            return MultimodalResult(success=False, error=f"TTS 失败: {exc}")


class MultimodalEngine:
    """统一多模态入口"""

    def __init__(self) -> None:
        self.vision = VisionEngine()
        self.audio = AudioEngine()

    def capabilities(self) -> Dict[str, Any]:
        return {
            "vision": _CapabilityDetector.get_vision_capabilities(),
            "audio": _CapabilityDetector.get_audio_capabilities(),
        }

    def describe_image(self, image_path: str, prompt: str = "描述这张图片") -> Dict[str, Any]:
        return self.vision.describe(image_path, prompt).to_dict()

    def transcribe_audio(self, audio_path: str, language: str = "zh") -> Dict[str, Any]:
        return self.audio.transcribe(audio_path, language).to_dict()

    def text_to_speech(self, text: str, output_path: Optional[str] = None, voice: str = "zh-CN-XiaoxiaoNeural") -> Dict[str, Any]:
        return self.audio.speak(text, output_path, voice).to_dict()

    def image_to_base64(self, image_path: str) -> Optional[str]:
        return self.vision.to_base64(image_path)


# 全局多模态引擎实例
multimodal = MultimodalEngine()
