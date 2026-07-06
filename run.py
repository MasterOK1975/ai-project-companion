#!/usr/bin/env python3
"""
AI Project Companion — Container Entry Point.
Запускает бота в режиме long polling + HTTP health check для Serverless Containers.
"""
import os
import sys
import asyncio
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler

# Добавляем путь к корню проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from bot.main import main as run_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "8080"))


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Простой HTTP-сервер для health check от Yandex Cloud."""

    def do_get(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        logger.info(f"Health check: {format % args}")


def run_health_server():
    """Запускает HTTP-сервер health check в отдельном потоке."""
    server = HTTPServer(("0.0.0.0", PORT), HealthCheckHandler)
    logger.info(f"Health check server running on port {PORT}")
    server.serve_forever()


def main():
    """Запускает health check сервер и бота."""
    import threading

    # Запускаем health check в отдельном потоке
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    # Запускаем бота в режиме long polling
    logger.info("Starting bot in long polling mode...")
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()