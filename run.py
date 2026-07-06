#!/usr/bin/env python3
"""
AI Project Companion — Container Entry Point.
Запускает aiohttp HTTP-сервер для приёма вебхуков от Telegram.
"""

import os
import sys
import json
import logging

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiohttp import web

from bot.main import process_update, bot, dp, db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "8080"))


async def handle_health(request):
    """Health check для Yandex Cloud."""
    return web.Response(text="OK")


async def handle_webhook(request):
    """Обработка входящего вебхука от Telegram."""
    try:
        body = await request.json()
        logger.info(f"Received update: {list(body.keys()) if isinstance(body, dict) else 'not dict'}")

        # Подключаемся к БД
        await db.connect()

        # Используем существующую логику обработки из bot/main.py
        from aiogram.types import Update
        telegram_update = Update.model_validate(body, context={"bot": bot})
        await dp.feed_update(bot, telegram_update)

        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return web.Response(text="OK")
    finally:
        await db.close()


async def on_startup(app):
    """Действия при запуске приложения."""
    logger.info("Starting AI Project Companion webhook server...")
    await db.connect()
    logger.info("Database connected")


async def on_shutdown(app):
    """Действия при остановке приложения."""
    logger.info("Shutting down...")
    await db.close()
    logger.info("Database closed")


def create_app():
    """Создание и настройка aiohttp приложения."""
    app = web.Application()

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    app.router.add_get("/", handle_health)
    app.router.add_post("/", handle_webhook)

    return app


if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=PORT)