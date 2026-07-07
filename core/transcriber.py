# AI Project Companion — Core: Speech Transcriber
"""
Модуль распознавания речи из аудио и видео файлов.
Использует Groq Whisper API (бесплатно, быстро).
Перед отправкой сжимает аудио через ffmpeg в opus 24kbps,
чтобы не превышать лимит Groq ~25 MB.
"""

import os
import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SpeechTranscriber:
    """Распознавание речи из аудио/видео файлов"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = "whisper-large-v3"
        self.base_url = "https://api.groq.com/openai/v1/audio/transcriptions"

    async def transcribe(self, file_bytes: bytes, filename: str = "audio.mp3") -> Optional[str]:
        """
        Распознавание речи из аудио/видео файла через Groq Whisper.

        Args:
            file_bytes: Бинарные данные файла
            filename: Имя файла (для определения формата)

        Returns:
            str: Распознанный текст или None при ошибке
        """
        try:
            if not self.api_key:
                logger.warning("No GROQ_API_KEY set")
                return "[Распознавание речи недоступно — не указан GROQ_API_KEY]"

            # Сжимаем аудио через ffmpeg перед отправкой
            compressed = self._compress_audio(file_bytes)
            if compressed is None:
                logger.error("Audio compression failed, sending original")
                compressed = file_bytes

            return await self._transcribe_groq(compressed, filename)

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    def _compress_audio(self, file_bytes: bytes) -> Optional[bytes]:
        """
        Сжимает аудио через ffmpeg в opus 24kbps.
        Opus при 24kbps даёт ~1.8 MB на 10 минут — влезает в лимит Groq.
        """
        import tempfile

        try:
            with tempfile.NamedTemporaryFile(suffix='.input', delete=False) as tmp_in:
                tmp_in.write(file_bytes)
                tmp_in_path = tmp_in.name

            tmp_out_path = tmp_in_path + '.opus'

            result = subprocess.run(
                ['ffmpeg', '-y', '-i', tmp_in_path,
                 '-c:a', 'libopus', '-b:a', '24k',
                 '-application', 'lowdelay',
                 tmp_out_path],
                capture_output=True,
                timeout=120
            )

            if result.returncode != 0:
                logger.error(f"ffmpeg error: {result.stderr.decode()[:500]}")
                return None

            with open(tmp_out_path, 'rb') as f:
                compressed = f.read()

            logger.info(f"Compressed audio: {len(file_bytes)} -> {len(compressed)} bytes")

            return compressed

        except subprocess.TimeoutExpired:
            logger.error("ffmpeg compression timed out")
            return None
        except Exception as e:
            logger.error(f"Compression error: {e}")
            return None
        finally:
            # Чистим временные файлы
            for p in [tmp_in_path, tmp_out_path]:
                try:
                    os.unlink(p)
                except Exception:
                    pass

    async def _transcribe_groq(self, file_bytes: bytes, filename: str) -> str:
        """Транскрибация через Groq Whisper API"""
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        data = aiohttp.FormData()
        data.add_field(
            "file",
            file_bytes,
            filename=filename,
            content_type="application/octet-stream"
        )
        data.add_field("model", self.model)
        data.add_field("language", "ru")
        data.add_field("response_format", "json")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.base_url,
                headers=headers,
                data=data
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Groq Whisper error {resp.status}: {error_text}")

                result = await resp.json()
                return result.get("text", "")