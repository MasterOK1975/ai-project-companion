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
import asyncio

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, Update
from aiogram.utils.markdown import text, bold

from telethon import TelegramClient

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
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////tmp/data.db")

# Telethon — MTProto клиент для скачивания файлов >20 MB
# (Bot API ограничен 20 MB, MTProto позволяет до 2 ГБ)
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "2040"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "b18441a1ff607e10a989891a5462e627")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Telethon клиент (ленивая инициализация — подключается при первом скачивании)
telethon_client = TelegramClient('bot_session', TELEGRAM_API_ID, TELEGRAM_API_HASH)

# Инициализация компонентов
db = Database(DATABASE_URL)
transcriber = SpeechTranscriber()
analyzer = ProjectAnalyzer(api_key=OPENROUTER_API_KEY)
tz_analyzer = TZAnalyzer(api_key=OPENROUTER_API_KEY)
chat_analyzer = ChatAnalyzer(api_key=OPENROUTER_API_KEY)

# Состояния для пошагового взаимодействия
class ProjectStates(StatesGroup):
    waiting_for_name = State()

class TZStates(StatesGroup):
    waiting_for_text = State()

class ChatStates(StatesGroup):
    waiting_for_text = State()

# Единый event loop для всех вызовов Yandex Cloud Functions
# (создаётся один раз при холодном старте и переиспользуется)
_shared_loop: asyncio.AbstractEventLoop = None


def _get_loop() -> asyncio.AbstractEventLoop:
    """Возвращает единый event loop, создавая его при первом вызове"""
    global _shared_loop
    if _shared_loop is None or _shared_loop.is_closed():
        _shared_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_shared_loop)
    return _shared_loop


async def _send_long_message(message: Message, text_content: str):
    """Отправляет длинное сообщение, разбивая на части по 4000 символов"""
    MAX_LEN = 4000
    if len(text_content) <= MAX_LEN:
        await message.answer(text_content)
        return

    parts = []
    current = ""
    for line in text_content.split("\n"):
        if len(current) + len(line) + 1 > MAX_LEN:
            parts.append(current)
            current = line
        else:
            if current:
                current += "\n" + line
            else:
                current = line
    if current:
        parts.append(current)

    for part in parts:
        await message.answer(part)


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
async def cmd_new_project(message: Message, state: FSMContext):
    """Создание нового проекта — пошагово"""
    parts = message.text.split(maxsplit=1)
    if len(parts) >= 2:
        # Если название передано сразу — создаём
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
    else:
        # Запрашиваем название
        await state.set_state(ProjectStates.waiting_for_name)
        await message.answer("📝 Введите название нового проекта:")


@dp.message(ProjectStates.waiting_for_name)
async def process_project_name(message: Message, state: FSMContext):
    """Обработка введённого названия проекта"""
    project_name = message.text.strip()
    user_id = str(message.from_user.id)

    project = await db.create_project(
        user_id=user_id,
        name=project_name,
        username=message.from_user.username
    )

    await state.clear()

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
            "Создай первый: /new_project"
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
async def cmd_analyze_tz(message: Message, state: FSMContext):
    """Анализ технического задания — пошагово"""
    parts = message.text.split(maxsplit=1)
    if len(parts) >= 2:
        # Если текст передан сразу — анализируем
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

            await _send_long_message(message, report)

        except Exception as e:
            logger.error(f"Error analyzing TZ: {e}")
            await message.answer("❌ Произошла ошибка при анализе ТЗ. Попробуй ещё раз.")
    else:
        # Запрашиваем текст ТЗ
        await state.set_state(TZStates.waiting_for_text)
        await message.answer(
            "📄 Отправьте текст технического задания.\n\n"
            "Можно скопировать текст из Google Docs, PDF, Word или любого другого источника."
        )


@dp.message(TZStates.waiting_for_text)
async def process_tz_text(message: Message, state: FSMContext):
    """Обработка введённого текста ТЗ"""
    tz_text = message.text.strip()
    await state.clear()

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

        await _send_long_message(message, report)

    except Exception as e:
        logger.error(f"Error analyzing TZ: {e}")
        await message.answer("❌ Произошла ошибка при анализе ТЗ. Попробуй ещё раз.")


@dp.message(Command("analyze_chat"))
async def cmd_analyze_chat(message: Message, state: FSMContext):
    """Анализ переписки с заказчиком — пошагово"""
    parts = message.text.split(maxsplit=1)
    if len(parts) >= 2:
        # Если текст передан сразу — анализируем
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

            await _send_long_message(message, report)

        except Exception as e:
            logger.error(f"Error analyzing chat: {e}")
            await message.answer("❌ Произошла ошибка при анализе переписки. Попробуй ещё раз.")
    else:
        # Запрашиваем текст переписки
        await state.set_state(ChatStates.waiting_for_text)
        await message.answer(
            "💬 Отправьте текст переписки.\n\n"
            "Желательно обозначать участников как «Клиент:» и «Исполнитель:».\n"
            "Можно также просто скопировать переписку целиком."
        )


@dp.message(ChatStates.waiting_for_text)
async def process_chat_text(message: Message, state: FSMContext):
    """Обработка введённого текста переписки"""
    chat_text = message.text.strip()
    await state.clear()

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

        await _send_long_message(message, report)

    except Exception as e:
        logger.error(f"Error analyzing chat: {e}")
        await message.answer("❌ Произошла ошибка при анализе переписки. Попробуй ещё раз.")


@dp.message(F.text)
async def handle_text(message: Message):
    """Обработка текстовых сообщений (не команд)"""
    if message.text.startswith("/"):
        return

    user_id = str(message.from_user.id)
    text_content = message.text

    await message.answer("✅ Текст получен, начинаю анализ...")

    try:
        project = await db.get_active_project(user_id)
        if not project:
            project = await db.create_project(
                user_id=user_id,
                name=f"Проект от {message.date.strftime('%d.%m.%Y')}",
                username=message.from_user.username
            )

        await message.answer("🧠 Анализирую текст созвона...")

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


@dp.message(F.audio | F.video | F.voice)
async def handle_audio_video(message: Message):
    """Обработка аудио и видео файлов"""
    user_id = str(message.from_user.id)
    file_type = "аудио" if message.audio or message.voice else "видео"

    # Мгновенное подтверждение получения
    await message.answer(f"✅ {file_type.capitalize()} получен, начинаю обработку...")

    try:
        # Скачиваем через Telethon (MTProto) — нет лимита 20 MB
        # Telethon находит сообщение по chat_id и message_id, затем скачивает медиа
        if not telethon_client.is_connected():
            await telethon_client.start(bot_token=BOT_TOKEN)

        chat = await telethon_client.get_entity(message.chat.id)
        msg = await telethon_client.get_messages(chat, ids=message.message_id)
        file_bytes = await telethon_client.download_media(msg, file=bytes)

        if not file_bytes:
            await message.answer("❌ Не удалось скачать файл.")
            return

        project = await db.get_active_project(user_id)
        if not project:
            project = await db.create_project(
                user_id=user_id,
                name=f"Созвон от {message.date.strftime('%d.%m.%Y')}",
                username=message.from_user.username
            )

        await message.answer("🎙 Распознаю речь...")

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

    await _send_long_message(message, report)


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
    Использует единый event loop, созданный при холодном старте,
    чтобы избежать ошибки "Event loop is closed" на повторных вызовах.
    """
    # Защита от None event
    if event is None:
        event = {}

    logger.info(f"Handler called, event keys: {list(event.keys()) if isinstance(event, dict) else 'not dict'}")

    # Тело запроса может быть как строкой (JSON), так и уже распарсенным dict
    body = event.get('body', '{}')

    # Если body пустая строка — используем весь event как тело
    if isinstance(body, str) and not body.strip():
        logger.info("Body is empty, using event as body")
        body = event

    # Если body уже dict — используем как есть
    if isinstance(body, dict):
        update_data = body
    else:
        # Парсим строку JSON
        try:
            update_data = json.loads(body)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f"Failed to parse body: {e}, body type={type(body)}, body={str(body)[:500]}")
            return {"statusCode": 200, "body": "ok"}

    # Используем единый event loop вместо создания нового на каждый вызов
    loop = _get_loop()
    try:
        result = loop.run_until_complete(process_update(update_data))
    finally:
        # НЕ закрываем loop — он будет переиспользован следующими вызовами
        pass

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
    asyncio.run(main())