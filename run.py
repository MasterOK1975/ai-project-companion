#!/usr/bin/env python3
"""
AI Project Companion — Container Entry Point.
Принимает вебхуки от Telegram и передаёт в bot.main.process_update
"""
import os
import sys
import asyncio
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from aiohttp import web
from bot.main import process_update

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "8080"))


async def handle_health(request):
    return web.Response(text="OK")


async def handle_webhook(request):
    try:
        body = await request.json()
        logger.info("Webhook received from Telegram")

        # Возвращаем 200 мгновенно, чтобы Telegram не ретраил.
        # Обработка (скачивание, ffmpeg, Groq, OpenRouter) идёт в фоне.
        asyncio.ensure_future(process_update(body))

        return web.json_response({"statusCode": 200, "body": ""})
    except Exception as e:
        logger.error(f"Webhook error: {e}", exc_info=True)
        return web.Response(text="OK")


app = web.Application()
app.router.add_get("/", handle_health)
app.router.add_post("/", handle_webhook)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=PORT)