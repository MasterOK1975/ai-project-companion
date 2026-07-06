# AI Project Companion — Telegram Bot
"""
Модуль Telegram-бота для AI Project Companion.
Поддерживает два режима:
- Локальный: long polling (python -m bot.main)
- Yandex Cloud Functions: webhook (через handler)

Команды:
- /start — приветствие
- /help — подробная справка
- /new_project — создать новый проект
- /projects — список проектов
- /select_project — выбрать проект
- /analyze_tz — анализ технического задания
- /analyze_chat — анализ переписки с заказчиком
"""

import os
import sys
import json
import logging

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, Update
from aiogram.utils.markdown import text, bold

from core.analyzer import ProjectAnalyzer
from core.transcriber import SpeechTranscriber
from core.tz_analyzer import TZAnalyzer
from core.chat_analyzer import ChatAnalyzer
from db.database import Database

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///tmp/data.db")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация компонентов
db = Database(DATABASE_URL)
transcriber = SpeechTranscriber()
analyzer = ProjectAnalyzer(api_key=OPENROUTER_API_KEY)
tz_analyzer = TZAnalyzer(api_key=OPENROUTER_API_KEY)
chat_analyzer = ChatAnalyzer(api_key=OPENROUTER_API_KEY)


@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Приветственное сообщение"""
    await message.answer(
        text(
            bold("🧠 AI Project Companion"),
            "",
            "Привет! Я AI-помощник по ведению проектов.",
            "",
            "Я могу:",
            "🎙 Расшифровать аудио/видео созвона",
            "📝 Сделать краткое саммари",
            "✅ Составить список задач",
            "📊 Отследить изменения в проекте",
            "💾 Сохранить историю проекта",
            "📄 Проанализировать техническое задание",
            "💬 Сделать мини-брифинг из переписки с клиентом",
            "",
            "Команды:",
            "/start — показать это сообщение",
            "/help — подробная справка",
            "/new_project — создать новый проект",
            "/projects — список проектов",
            "/analyze_tz — анализ технического задания",
            "/analyze_chat — анализ переписки с заказчиком",
            sep="\n"
        )
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Подробная справка"""
    await message.answer(
        text(
            bold("📖 Как пользоваться AI Project Companion"),
            "",
            "1️⃣ Создай проект: /new_project Название проекта",
            "2️⃣ Загрузи аудио/видео созвона или отправь текст",
            "3️⃣ Дождись анализа — я пришлю отчёт",
            "4️⃣ Смотри историю: /projects",
            "",
            bold("Поддерживаемые форматы:"),
            "🎵 Аудио: MP3, WAV, OGG, M4A",
            "🎬 Видео: MP4, AVI, MOV",
            "📄 Текст: просто отправь сообщение",
            "",
            bold("Анализ ТЗ:"),
            "📄 /analyze_tz — вставь текст ТЗ и получи разбор:",
            "   • саммари и видение реализации",
            "   • этапы работ и зоны ответственности",
            "   • открытые вопросы и риски",
            "   • рекомендации по улучшению ТЗ",
            "",
            bold("Анализ переписки:"),
            "💬 /analyze_chat — отправь переписку с клиентом:",
            "   • саммари и информация о клиенте",
            "   • договорённости и задачи",
            "   • открытые вопросы и следующие шаги",
            "   • рекомендации по коммуникации",
            "",
            bold("Что я формирую для созвонов:"),
            "📝 Полная расшифровка по ролям",
            "📋 Краткое саммари",
            "✅ Список задач (исполнитель / заказчик)",
            "🔄 Что изменилось с прошлого раза",
            "⚠️ Новые требования (Scope Control)",
            "📊 История версий проекта",
            sep="\n"
        )
    )


@dp.message(Command("new_project"))
async def cmd_new_project(message: Message):
    """Создание нового проекта"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "📝 Укажи название проекта после команды.\n"
            "Пример: /new_project Разработка сайта"
        )
        return

    project_name = parts[1].strip()
    user_id = str(message.from_user.id)

    project = await db.create_project(
        user_id=user_id,
        name=project_name,
        username=message.from_user.username
    )

    await message.answer(
        text(
            bold(f"✅ Проект «{project_name}» создан!"),
            f"ID проекта: {project['id']}",
            "",
            "Теперь отправь мне аудио, видео или текст созвона.",
            sep="\n"
        )
    )


@dp.message(Command("projects"))
async def cmd_projects(message: Message):
    """Список проектов пользователя"""
    user_id = str(message.from_user.id)
    projects = await db.get_user_projects(user_id)

    if not projects:
        await message.answer(
            "📭 У тебя пока нет проектов.\n"
            "Создай первый: /new_project Название"
        )
        return

    text_parts = [bold("📂 Твои проекты:"), ""]
    for p in projects:
        text_parts.append(f"🔹 {p['name']} (ID: {p['id']})")
        text_parts.append(f"   Созвонов: {p['meeting_count']}")

    text_parts.append("")
    text_parts.append("Чтобы выбрать проект, используй:")
    text_parts.append("/select_project ID_проекта")

    await message.answer(text(*text_parts, sep="\n"))


@dp.message(Command("select_project"))
async def cmd_select_project(message: Message):
    """Выбор активного проекта"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажи ID проекта: /select_project 1")
        return

    project_id = int(parts[1])
    user_id = str(message.from_user.id)

    project = await db.get_project(project_id)
    if not project or project['user_id'] != user_id:
        await message.answer("❌ Проект не найден или не принадлежит тебе.")
        return

    await message.answer(
        text(
            bold(f"✅ Проект «{project['name']}» выбран!"),
            "Теперь отправь мне аудио, видео или текст для анализа.",
            sep="\n"
        )
    )


@dp.message(Command("analyze_tz"))
async def cmd_analyze_tz(message: Message):
    """Анализ технического задания"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "📄 Отправь текст технического задания после команды.\n\n"
            "Пример:\n"
            "/analyze_tz Название проекта: Разработка мобильного приложения...\n\n"
            "Можно скопировать текст из Google Docs, PDF, Word или любого другого источника."
        )
        return

    tz_text = parts[1].strip()
    await message.answer("📄 Анализирую техническое задание...")

    try:
        result = await tz_analyzer.analyze(tz_text)

        report = text(
            bold("📄 Анализ технического задания"),
            "",
            bold("📋 Саммари:"),
            result.get('summary', ''),
            "",
            bold("👁 Видение реализации:"),
            result.get('vision', ''),
            "",
            bold("📅 Этапы работ:"),
            _format_list(result.get('stages', [])),
            "",
            bold("👥 Зоны ответственности:"),
            result.get('responsibilities', ''),
            "",
            bold("❓ Открытые вопросы:"),
            result.get('open_questions', ''),
            "",
            bold("⚠️ Риски:"),
            result.get('risks', ''),
            "",
            bold("💡 Рекомендации:"),
            result.get('recommendations', ''),
            "",
            bold("📊 Оценка сложности:"),
            result.get('estimated_complexity', ''),
            "",
            bold("📌 Отсутствующие разделы:"),
            _format_list(result.get('missing_sections', [])),
            sep="\n"
        )

        await message.answer(report)

    except Exception as e:
        logger.error(f"Error analyzing TZ: {e}")
        await message.answer("❌ Произошла ошибка при анализе ТЗ. Попробуй ещё раз.")


@dp.message(Command("analyze_chat"))
async def cmd_analyze_chat(message: Message):
    """Анализ переписки с заказчиком"""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "💬 Отправь текст переписки после команды.\n\n"
            "Пример:\n"
            "/analyze_chat Клиент: Привет! Нужен сайт для магазина\n"
            "Исполнитель: Здравствуйте! Расскажите подробнее...\n\n"
            "Желательно обозначать участников как «Клиент:» и «Исполнитель:».\n"
            "Можно также просто скопировать переписку целиком."
        )
        return

    chat_text = parts[1].strip()
    await message.answer("💬 Анализирую переписку...")

    try:
        result = await chat_analyzer.analyze(chat_text)

        report = text(
            bold("💬 Мини-брифинг по переписке"),
            "",
            bold("📋 Саммари:"),
            result.get('summary', ''),
            "",
            bold("👤 О клиенте:"),
            result.get('client_info', ''),
            "",
            bold("✅ Договорённости:"),
            result.get('agreed', ''),
            "",
            bold("📌 Задачи исполнителя:"),
            _format_list(result.get('executor_tasks', [])),
            "",
            bold("📌 Задачи заказчика:"),
            _format_list(result.get('client_tasks', [])),
            "",
            bold("❓ Открытые вопросы:"),
            result.get('open_questions', ''),
            "",
            bold("⚖️ Требуются решения:"),
            result.get('decisions_needed', ''),
            "",
            bold("🚀 Следующие шаги:"),
            result.get('next_steps', ''),
            "",
            bold("⚠️ Риски:"),
            result.get('risks', ''),
            "",
            bold("💡 Рекомендации:"),
            result.get('recommendations', ''),
            sep="\n"
        )

        await message.answer(report)

    except Exception as e:
        logger.error(f"Error analyzing chat: {e}")
        await message.answer("❌ Произошла ошибка при анализе переписки. Попробуй ещё раз.")


@dp.message()
async def handle_text(message: Message):
    """Обработка текстовых сообщений"""
    if message.text and message.text.startswith("/"):
        return

    if not message.text:
        return

    user_id = str(message.from_user.id)
    text_content = message.text

    await message.answer("🧠 Анализирую текст созвона...")

    try:
        project = await db.get_active_project(user_id)
        if not project:
            project = await db.create_project(
                user_id=user_id,
                name=f"Проект от {message.date.strftime('%d.%m.%Y')}",
                username=message.from_user.username
            )

        result = await analyzer.analyze_meeting(
            text=text_content,
            project_id=project['id'],
            project_history=await db.get_project_history(project['id'])
        )

        meeting = await db.save_meeting(
            project_id=project['id'],
            text=text_content,
            analysis=result
        )

        await send_analysis_report(message, result, meeting['version'])

    except Exception as e:
        logger.error(f"Error analyzing text: {e}")
        await message.answer("❌ Произошла ошибка при анализе. Попробуй ещё раз.")


@dp.message()
async def handle_audio_video(message: Message):
    """Обработка аудио и видео файлов"""
    if not message.audio and not message.video and not message.voice:
        return

    user_id = str(message.from_user.id)
    file_type = "аудио" if message.audio or message.voice else "видео"

    await message.answer(f"🎵 Получил {file_type}. Начинаю обработку...")

    try:
        if message.audio:
            file_id = message.audio.file_id
        elif message.voice:
            file_id = message.voice.file_id
        else:
            file_id = message.video.file_id

        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)

        project = await db.get_active_project(user_id)
        if not project:
            project = await db.create_project(
                user_id=user_id,
                name=f"Созвон от {message.date.strftime('%d.%m.%Y')}",
                username=message.from_user.username
            )

        await message.answer("🎙 Ра��познаю речь...")

        text = await transcriber.transcribe(file_bytes)

        if not text:
            await message.answer("❌ Не удалось распознать речь. Попробуй другой файл.")
            return

        await message.answer("🧠 Анализирую содержание...")

        result = await analyzer.analyze_meeting(
            text=text,
            project_id=project['id'],
            project_history=await db.get_project_history(project['id'])
        )

        meeting = await db.save_meeting(
            project_id=project['id'],
            text=text,
            analysis=result,
            file_type=file_type
        )

        await send_analysis_report(message, result, meeting['version'])

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await message.answer("❌ Произошла ошибка при обработке. Попробуй ещё раз.")


async def send_analysis_report(message: Message, result: dict, version: int):
    """Отправка отчёта пользователю"""
    report = text(
        bold(f"📊 Отчёт по созвону (Версия {version})"),
        "",
        bold("📝 Расшифровка:"),
        result.get('transcript', '')[:500] + "..." if len(result.get('transcript', '')) > 500 else result.get('transcript', ''),
        "",
        bold("📋 Саммари:"),
        result.get('summary', ''),
        "",
        bold("✅ Задачи исполнителя:"),
        _format_tasks(result.get('executor_tasks', [])),
        "",
        bold("✅ Задачи заказчика:"),
        _format_tasks(result.get('client_tasks', [])),
        "",
        bold("🔄 Что изменилось:"),
        result.get('changes', 'Нет изменений'),
        "",
        bold("⚠️ Новые требования:"),
        result.get('new_requirements', 'Не обнаружено'),
        "",
        bold("📌 Согласовано:"),
        result.get('agreed', ''),
        "",
        bold("❓ Открытые вопросы:"),
        result.get('open_questions', 'Нет'),
        "",
        bold("📅 Следующий созвон:"),
        result.get('next_meeting', 'Не назначен'),
        sep="\n"
    )

    await message.answer(report)


def _format_tasks(tasks: list) -> str:
    """Форматирование списка задач"""
    if not tasks:
        return "Нет задач"
    return "\n".join(f"• {task}" for task in tasks)


def _format_list(items: list) -> str:
    """Форматирование списка"""
    if not items:
        return "Нет"
    return "\n".join(f"• {item}" for item in items)


# ========== Yandex Cloud Functions Handler ==========

async def process_update(update_data: dict) -> dict:
    """Обработка входящего обновления от Telegram"""
    try:
        # Подключаемся к БД
        await db.connect()

        # Создаём объект Update из данных
        telegram_update = Update.model_validate(update_data, context={"bot": bot})

        # Обрабатываем через диспетчер
        await dp.feed_update(bot, telegram_update)

        return {"statusCode": 200, "body": ""}
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return {"statusCode": 200, "body": ""}
    finally:
        await db.close()


def handler(event, context):
    """
    Точка входа для Yandex Cloud Functions.
    Вызывается при каждом POST-запросе от Telegram.
    """
    import asyncio

    # Тело запроса может быть как строкой (JSON), так и уже распарсенным dict
    body = event.get('body', '{}')
    if isinstance(body, str):
        body = json.loads(body)

    # Обрабатываем обновление
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(process_update(body))
    loop.close()

    return result


# ========== Local Development ==========

async def main():
    """Запуск бота в режиме long polling (для локальной разработки)"""
    logger.info("Starting AI Project Companion bot in polling mode...")
    await db.connect()
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())