"""
PRISM Agent - Voice Interaction
语音输入 + 流式语音输出，桌面端 Hands-free 交互
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger("prism.voice")

try:
    import speech_recognition as sr  # type: ignore[import-untyped]

    _SR_AVAILABLE = True
except Exception:  # noqa: BLE001
    _SR_AVAILABLE = False

try:
    import edge_tts  # type: ignore[import-untyped]

    _EDGE_TTS_AVAILABLE = True
except Exception:  # noqa: BLE001
    _EDGE_TTS_AVAILABLE = False


class VoiceInteraction:
    """语音交互：麦克风输入 -> 文字；文字 -> 语音输出。"""

    def __init__(
        self,
        stt_engine: str = "google",
        tts_engine: str = "edge",
        language: str = "zh-CN",
        output_dir: Optional[Path] = None,
    ) -> None:
        self.stt_engine = stt_engine
        self.tts_engine = tts_engine
        self.language = language
        self.output_dir = Path(output_dir) if output_dir else Path(tempfile.gettempdir()) / "prism_voice"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._stop_event = threading.Event()

    @property
    def available(self) -> bool:
        return _SR_AVAILABLE or _EDGE_TTS_AVAILABLE

    def listen(self, timeout: int = 5, phrase_time_limit: int = 15) -> str:
        """
        从麦克风监听并转写为文字。
        Returns: 转写文本；失败返回空字符串。
        """
        if not _SR_AVAILABLE:
            logger.warning("speech_recognition not installed, cannot listen")
            return ""
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            if self.stt_engine == "google":
                return recognizer.recognize_google(audio, language=self.language)
            if self.stt_engine == "whisper":
                try:
                    import openai  # type: ignore[import-untyped]

                    client = openai.OpenAI()
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                        f.write(audio.get_wav_data())
                        wav_path = f.name
                    try:
                        with open(wav_path, "rb") as wf:
                            transcript = client.audio.transcriptions.create(model="whisper-1", file=wf, language=self.language[:2])
                        return transcript.text
                    finally:
                        try:
                            os.unlink(wav_path)
                        except OSError:
                            pass
                except Exception as exc:
                    logger.debug("whisper stt failed: %s", exc)
                    return ""
            logger.warning("unsupported stt engine: %s", self.stt_engine)
            return ""
        except sr.WaitTimeoutError:
            logger.debug("listen timeout")
            return ""
        except Exception as exc:
            logger.warning("listen failed: %s", exc)
            return ""

    def speak(self, text: str, voice: str = "zh-CN-XiaoxiaoNeural", stop_event: Optional[threading.Event] = None) -> Optional[Path]:
        """
        文字转语音并播放。
        Returns: 生成的音频文件路径；失败返回 None。
        """
        text = (text or "").strip()
        if not text:
            return None
        if self.tts_engine != "edge":
            logger.warning("only edge tts supported in this build")
            return None
        if not _EDGE_TTS_AVAILABLE:
            logger.warning("edge-tts not installed, cannot speak")
            return None
        try:
            import asyncio

            async def _generate() -> Optional[Path]:
                communicate = edge_tts.Communicate(text, voice)
                out_path = self.output_dir / f"tts_{hash(text) % 10**8}.mp3"
                try:
                    await communicate.save(str(out_path))
                    return out_path
                except Exception as exc:
                    logger.debug("edge tts save failed: %s", exc)
                    return None

            loop = asyncio.new_event_loop()
            try:
                path = loop.run_until_complete(_generate())
            finally:
                loop.close()
            if path is None or not path.exists():
                return None
            self._play_audio(path, stop_event=stop_event)
            return path
        except Exception as exc:
            logger.warning("speak failed: %s", exc)
            return None

    def _play_audio(self, path: Path, stop_event: Optional[threading.Event] = None) -> None:
        """播放音频文件，不阻塞主线程。"""
        def _worker() -> None:
            try:
                import simpleaudio  # type: ignore[import-untyped]
                import wave

                with wave.open(str(path), "rb") as wf:
                    data = wf.readframes(wf.getnframes())
                    channels = wf.getnchannels()
                    width = wf.getsampwidth()
                    rate = wf.getframerate()
                play_obj = simpleaudio.play_buffer(data, channels, width, rate)
                while play_obj.is_playing():
                    if stop_event and stop_event.is_set():
                        play_obj.stop()
                        break
                    threading.Event().wait(0.1)
            except Exception:
                try:
                    os.startfile(path)  # type: ignore[attr-defined]
                except Exception as exc:
                    logger.debug("fallback play failed: %s", exc)

        threading.Thread(target=_worker, daemon=True).start()

    def stop(self) -> None:
        self._stop_event.set()


__all__ = ["VoiceInteraction"]
