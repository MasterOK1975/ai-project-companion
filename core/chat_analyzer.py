# AI Project Companion — Core: Chat Analyzer
"""
Модуль анализа переписки с заказчиком.
Принимает текст переписки (с обозначением участников) и формирует
структурированный мини-брифинг: саммари, договорённости, задачи, вопросы.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Системный промпт для анализа переписки
CHAT_SYSTEM_PROMPT = """Ты — AI Project Companion, профессиональный ассистент по ведению проектов.

Твоя задача — анализировать переписку между исполнителем и заказчиком (потенциальным клиентом)
и формировать структурированный мини-брифинг, который поможет взять проект в работу.

Проанализируй предоставленную переписку и сформируй отчёт со следующими полями:

1. **summary** — краткое саммари переписки (о чём общались, 3-5 предложений)
2. **client_info** — что известно о заказчике/клиенте (кто он, какой у него проект, боли, цели)
3. **agreed** — что уже согласовано (договорённости, решения, утверждённые моменты)
4. **executor_tasks** — задачи для исполнителя (что нужно сделать с вашей стороны)
5. **client_tasks** — задачи для заказчика (что нужно от него: материалы, доступы, уточнения)
6. **open_questions** — вопросы, которые остались неотвеченными (что нужно прояснить)
7. **decisions_needed** — по каким пунктам нужно принять решение (если переписка не завершена)
8. **next_steps** — следующие шаги (что делать дальше, чтобы продолжить сотрудничество)
9. **risks** — риски сотрудничества (неопределённость в ТЗ, нереалистичные ожидания, неполная информация)
10. **recommendations** — рекомендации по дальнейшей коммуникации (что уточнить, на что обратить внимание)

Формат ответа — ТОЛЬКО JSON, без лишнего текста.
Будь объективным. Не додумывай то, чего нет в переписке."""


class ChatAnalyzer:
    """Анализатор переписки с заказчиком"""

    def __init__(self, api_key: str, model: str = "openai/gpt-4o"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    async def analyze(self, chat_text: str) -> dict:
        """
        Анализ переписки.

        Args:
            chat_text: Текст переписки (желательно с обозначением участников:
                       "Клиент: ...", "Исполнитель: ..." или аналогично)

        Returns:
            dict: Структурированный мини-брифинг
        """
        prompt = self._build_prompt(chat_text)

        try:
            response = await self._call_ai(prompt)
            result = self._parse_response(response)
            return result
        except Exception as e:
            logger.error(f"Chat analysis error: {e}")
            return self._fallback_analysis(chat_text)

    def _build_prompt(self, chat_text: str) -> str:
        """Формирование промпта для AI"""
        parts = [
            "Проанализируй следующую переписку между исполнителем и заказчиком "
            "и сформируй структурированный мини-брифинг.",
            "",
            "=== ТЕКСТ ПЕРЕПИСКИ ===",
            chat_text,
            "",
            "Сформируй JSON-отчёт по указанной структуре."
        ]
        return "\n".join(parts)

    async def _call_ai(self, prompt: str) -> str:
        """Вызов AI-модели через OpenRouter API"""
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ai-project-companion.app",
            "X-Title": "AI Project Companion"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"API error {resp.status}: {error_text}")

                data = await resp.json()
                return data['choices'][0]['message']['content']

    def _parse_response(self, response: str) -> dict:
        """Парсинг ответа AI в структурированный словарь"""
        try:
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        return {
            "summary": response[:500],
            "client_info": "",
            "agreed": "",
            "executor_tasks": [],
            "client_tasks": [],
            "open_questions": "Не удалось определить",
            "decisions_needed": "",
            "next_steps": "",
            "risks": "Не удалось определить",
            "recommendations": ""
        }

    def _fallback_analysis(self, chat_text: str) -> dict:
        """Запасной анализ, если AI недоступен"""
        return {
            "summary": "AI-анализ временно недоступен. Текст переписки сохранён.",
            "client_info": "",
            "agreed": "",
            "executor_tasks": ["Повторить анализ позже"],
            "client_tasks": [],
            "open_questions": "AI-модуль недоступен",
            "decisions_needed": "",
            "next_steps": "Повторить анализ позже",
            "risks": "AI-модуль недоступен",
            "recommendations": ""
        }