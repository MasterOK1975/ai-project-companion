# AI Project Companion — Core: Speech Transcriber
"""
Модуль распознавания речи из аудио и видео файлов.
Использует OpenAI Whisper API для транскрибации.
"""

import os
import io
import logging
import tempfile
from typing import Optional, BinaryIO

logger = logging.getLogger(__name__)


class SpeechTranscriber:
    """Распознавание речи из аудио/видео файлов"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = "whisper-1"

    async def transcribe(self, file_bytes: bytes, filename: str = "audio.mp3") -> Optional[str]:
        """
        Распознавание речи из аудио/видео файла.

        Args:
            file_bytes: Бинарные данные файла
            filename: Имя файла (для определения формата)

        Returns:
            str: Распознанный текст или None при ошибке
        """
        try:
            # Пробуем через OpenAI Whisper API
            if self.api_key:
                return await self._transcribe_openai(file_bytes, filename)

            # Если нет API-ключа — заглушка
            logger.warning("No API key for speech recognition")
            return "[Распознавание речи недоступно — не указан API-ключ OpenAI]"

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    async def _transcribe_openai(self, file_bytes: bytes, filename: str) -> str:
        """Транскрибация через OpenAI Whisper API"""
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        # Создаём multipart form data
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
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                data=data
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"Whisper API error {resp.status}: {error_text}")

                result = await resp.json()
                return result.get("text", "")

    async def transcribe_local(self, file_bytes: bytes) -> Optional[str]:
        """
        Локальная транскрибация (для будущего использования с локальными моделями).
        Заглушка — будет реализовано при использовании локальных моделей.
        """
        logger.info("Local transcription not yet implemented")
        return None