# AI Project Companion — Core: AI Analyzer
"""
Модуль анализа созвонов через AI-модели (OpenRouter).
Формирует структурированные отчёты: саммари, задачи, изменения, риски.
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Системный промпт для анализа созвонов
SYSTEM_PROMPT = """Ты — AI Project Companion, профессиональный ассистент по ведению проектов.

Твоя задача — анализировать созвоны (встречи) и формировать структурированный отчёт.

Для каждого созвона ты должен определить:

1. **transcript** — полная расшифровка разговора по ролям (кто что сказал)
2. **summary** — краткое саммари (о чём говорили, 3-5 предложений)
3. **executor_tasks** — список задач для исполнителя (массив строк)
4. **client_tasks** — список задач для заказчика (массив строк)
5. **agreed** — что было согласовано отдельным блоком
6. **changes** — что изменилось по сравнению с предыдущими созвонами
7. **new_requirements** — что является новым объёмом работ (если появилась задача, которой раньше не было — напиши "Обнаружено новое требование проекта. Рекомендуется пересогласовать стоимость и сроки.")
8. **scope_in** — что входит в текущий этап
9. **scope_out** — что НЕ входит в текущий этап
10. **paid_separately** — что требует дополнительной оплаты
11. **open_questions** — все вопросы без ответа
12. **risks** — риски проекта (изменение требований, отсутствие решения, неопределённость, конфликт ожиданий)
13. **next_meeting** — что необходимо обсудить на следующем созвоне

ВАЖНО: Если есть история предыдущих созвонов — сравнивай и показывай отличия.
Формат ответа — ТОЛЬКО JSON, без лишнего текста."""


class ProjectAnalyzer:
    """Анализатор созвонов через AI-модели"""

    def __init__(self, api_key: str, model: str = "google/gemini-2.0-flash-exp:free"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    async def analyze_meeting(
        self,
        text: str,
        project_id: int,
        project_history: Optional[list] = None,
        mode: str = "project"
    ) -> dict:
        """
        Анализ созвона через AI-модель.

        Args:
            text: Текст созвона (расшифровка или введённый текст)
            project_id: ID проекта
            project_history: История предыдущих созвонов (опционально)
            mode: Режим анализа ("project" или "consulting")

        Returns:
            dict: Структурированный отчёт
        """
        # Формируем промпт с учётом истории
        prompt = self._build_prompt(text, project_history, mode)

        try:
            response = await self._call_ai(prompt)
            result = self._parse_response(response)
            result['transcript'] = text
            return result
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return self._fallback_analysis(text)

    def _build_prompt(self, text: str, history: Optional[list], mode: str) -> str:
        """Формирование промпта для AI"""
        prompt_parts = []

        # Добавляем историю проекта, если есть
        if history:
            prompt_parts.append("=== ИСТОРИЯ ПРОЕКТА ===")
            for i, meeting in enumerate(history[-5:], 1):  # Последние 5 созвонов
                prompt_parts.append(f"\n--- Созвон {meeting['version']} ---")
                prompt_parts.append(f"Саммари: {meeting.get('summary', 'Нет данных')}")
                prompt_parts.append(f"Задачи: {meeting.get('executor_tasks', [])}")
                prompt_parts.append(f"Изменения: {meeting.get('changes', 'Нет')}")
            prompt_parts.append("\n=== ТЕКУЩИЙ СОЗВОН ===")

        # Добавляем режим
        if mode == "consulting":
            prompt_parts.append(
                "Режим: Консультация (психолог/коуч/наставник)\n"
                "Дополнительно определи:\n"
                "- рекомендации для клиента\n"
                "- план действий\n"
                "- домашнее задание\n"
                "- прогресс относительно предыдущих сессий"
            )

        prompt_parts.append(text)

        return "\n".join(prompt_parts)

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
                {"role": "system", "content": SYSTEM_PROMPT},
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
        # Пробуем распарсить JSON
        try:
            # Ищем JSON в ответе
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass

        # Если JSON не найден — возвращаем как есть
        return {
            "summary": response[:500],
            "executor_tasks": [],
            "client_tasks": [],
            "agreed": "",
            "changes": "",
            "new_requirements": "",
            "scope_in": "",
            "scope_out": "",
            "paid_separately": "",
            "open_questions": "",
            "risks": "",
            "next_meeting": ""
        }

    def _fallback_analysis(self, text: str) -> dict:
        """Запасной анализ, если AI недоступен"""
        return {
            "summary": "AI-анализ временно недоступен. Расшифровка сохранена.",
            "executor_tasks": ["Повторить анализ позже"],
            "client_tasks": [],
            "agreed": "",
            "changes": "",
            "new_requirements": "",
            "scope_in": "",
            "scope_out": "",
            "paid_separately": "",
            "open_questions": "",
            "risks": "AI-модуль недоступен",
            "next_meeting": ""
        }