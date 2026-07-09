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

    # Цепочка fallback-моделей при 429 ошибке
    FALLBACK_MODELS = [
        "qwen/qwen3-next-80b-a3b-instruct:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-4-31b-it:free",
        "qwen/qwen3-coder:free",
    ]

    def __init__(self, api_key: str, model: str = "qwen/qwen3-next-80b-a3b-instruct:free"):
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

        # Пробуем модели по цепочке при 429 ошибке
        models_to_try = [self.model] + [m for m in self.FALLBACK_MODELS if m != self.model]

        last_error = None
        for model in models_to_try:
            try:
                response = await self._call_ai(prompt, model)
                result = self._parse_response(response)
                return result
            except Exception as e:
                error_str = str(e)
                last_error = e
                # Если 429 — пробуем следующую модель
                if "429" in error_str or "Too Many Requests" in error_str or "ResourceExhausted" in error_str:
                    logger.warning(f"Model {model} rate limited (429), trying fallback...")
                    continue
                # Если модель недоступна — пробуем следующую
                if "404" in error_str or "unavailable" in error_str.lower():
                    logger.warning(f"Model {model} unavailable, trying fallback...")
                    continue
                # Другие ошибки — не ретраим
                logger.error(f"Chat analysis error with model {model}: {e}")
                break

        logger.error(f"All models failed, last error: {last_error}")
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

    async def _call_ai(self, prompt: str, model: str) -> str:
        """Вызов AI-модели через OpenRouter API"""
        import aiohttp

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://ai-project-companion.app",
            "X-Title": "AI Project Companion"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 4000
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(self.base_url, headers=headers, json=payload) as resp:
                data = await resp.json()

                # OpenRouter может вернуть ошибку в теле ответа даже при 200
                if "error" in data:
                    err = data["error"]
                    raise Exception(f"OpenRouter error: {err.get('message', 'unknown')} (code: {err.get('code', 'unknown')})")

                if resp.status != 200:
                    raise Exception(f"API error {resp.status}: {data}")

                if "choices" not in data:
                    raise Exception(f"OpenRouter response missing 'choices': {json.dumps(data, ensure_ascii=False)[:500]}")

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