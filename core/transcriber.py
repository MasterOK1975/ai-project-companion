# AI Project Companion — Core: Speech Transcriber
"""
Модуль распознавания речи из аудио и видео файлов.
Использует Groq Whisper API (бесплатно, быстро).
"""

import os
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
            if self.api_key:
                return await self._transcribe_groq(file_bytes, filename)

            logger.warning("No GROQ_API_KEY set")
            return "[Распознавание речи недоступно — не указан GROQ_API_KEY]"

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

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