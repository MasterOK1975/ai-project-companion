# AI Project Companion — Core: TZ Analyzer
"""
Модуль анализа технических заданий (ТЗ).
Принимает сырой текст ТЗ и формирует структурированный разбор:
саммари, видение, этапы работ, зоны ответственности, открытые вопросы.
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Системный промпт для анализа ТЗ
TZ_SYSTEM_PROMPT = """Ты — AI Project Companion, профессиональный ассистент по ведению проектов.

Твоя задача — анализировать технические задания (ТЗ) и формировать структурированный разбор,
который можно отправить заказчику, чтобы показать профессиональный подход к работе.

Проанализируй предоставленный текст ТЗ и сформируй отчёт со следующими полями:

1. **summary** — краткое саммари ТЗ (3-5 предложений, о чём проект)
2. **vision** — видение реализации: как ты видишь архитектуру, стек технологий, подход к разработке
3. **stages** — этапы работ (массив строк), разбивка проекта на логические этапы
4. **responsibilities** — зоны ответственности: что делает исполнитель, что делает заказчик
5. **open_questions** — все вопросы, которые не закрыты в ТЗ (что нужно прояснить, уточнить, детализировать)
6. **risks** — потенциальные риски проекта (неполнота ТЗ, неопределённость, технические сложности)
7. **recommendations** — рекомендации по улучшению ТЗ (чего не хватает, что стоит добавить)
8. **estimated_complexity** — оценка сложности проекта (low/medium/high) с пояснением
9. **missing_sections** — какие важные разделы отсутствуют в ТЗ (например, требования к безопасности, нефункциональные требования, интеграции)

Формат ответа — ТОЛЬКО JSON, без лишнего текста.
Будь объективным и конструктивным. Не додумывай то, чего нет в ТЗ."""


class TZAnalyzer:
    """Анализатор технических заданий"""

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

    async def analyze(self, tz_text: str) -> dict:
        """
        Анализ технического задания.

        Args:
            tz_text: Текст технического задания

        Returns:
            dict: Структурированный разбор ТЗ
        """
        prompt = self._build_prompt(tz_text)

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
                logger.error(f"TZ analysis error with model {model}: {e}")
                break

        logger.error(f"All models failed, last error: {last_error}")
        return self._fallback_analysis(tz_text)

    def _build_prompt(self, tz_text: str) -> str:
        """Формирование промпта для AI"""
        parts = [
            "Проанализируй следующее техническое задание и сформируй структурированный отчёт.",
            "",
            "=== ТЕКСТ ТЕХНИЧЕСКОГО ЗАДАНИЯ ===",
            tz_text,
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
                {"role": "system", "content": TZ_SYSTEM_PROMPT},
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
            "vision": "Не удалось сформировать видение",
            "stages": [],
            "responsibilities": "",
            "open_questions": "Не удалось определить",
            "risks": "Не удалось определить",
            "recommendations": "",
            "estimated_complexity": "Не удалось оценить",
            "missing_sections": []
        }

    def _fallback_analysis(self, tz_text: str) -> dict:
        """Запасной анализ, если AI недоступен"""
        return {
            "summary": "AI-анализ временно недоступен. Текст ТЗ сохранён.",
            "vision": "Повторите анализ позже",
            "stages": ["Повторить анализ позже"],
            "responsibilities": "",
            "open_questions": "AI-модуль недоступен",
            "risks": "AI-модуль недоступен",
            "recommendations": "",
            "estimated_complexity": "Не удалось оценить",
            "missing_sections": []
        }