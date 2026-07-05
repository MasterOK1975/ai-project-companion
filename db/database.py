# AI Project Companion — Database Module
"""
Модуль базы данных для хранения проектов, созвонов и истории.
Поддерживает SQLite (для разработки) и PostgreSQL (для продакшена).
"""

import os
import json
import logging
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    """Работа с базой данных проектов"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._conn = None

    async def connect(self):
        """Подключение к БД"""
        if self.database_url.startswith("sqlite"):
            import aiosqlite
            # Создаём директорию для данных
            os.makedirs("data", exist_ok=True)
            db_path = self.database_url.replace("sqlite:///", "")
            self._conn = await aiosqlite.connect(db_path)
            self._conn.row_factory = aiosqlite.Row
            await self._init_sqlite()
        else:
            # PostgreSQL
            import asyncpg
            self._conn = await asyncpg.connect(self.database_url)
            await self._init_postgres()

    async def _init_sqlite(self):
        """Инициализация таблиц для SQLite"""
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                mode TEXT DEFAULT 'project',
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                version INTEGER NOT NULL,
                text TEXT,
                analysis TEXT,
                file_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );
        """)
        await self._conn.commit()

    async def _init_postgres(self):
        """Инициализация таблиц для PostgreSQL"""
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id TEXT UNIQUE NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS projects (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                mode TEXT DEFAULT 'project',
                active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS meetings (
                id SERIAL PRIMARY KEY,
                project_id INTEGER NOT NULL REFERENCES projects(id),
                version INTEGER NOT NULL,
                text TEXT,
                analysis JSONB,
                file_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    async def create_project(self, user_id: str, name: str, username: str = None) -> dict:
        """Создание нового проекта"""
        # Убеждаемся, что пользователь существует
        await self._ensure_user(user_id, username)

        cursor = await self._conn.execute(
            "INSERT INTO projects (user_id, name) VALUES (?, ?)",
            (user_id, name)
        )
        await self._conn.commit()
        project_id = cursor.lastrowid

        return {
            "id": project_id,
            "name": name,
            "user_id": user_id,
            "meeting_count": 0
        }

    async def get_user_projects(self, user_id: str) -> list:
        """Получение списка проектов пользователя"""
        cursor = await self._conn.execute("""
            SELECT p.id, p.name, p.mode,
                   (SELECT COUNT(*) FROM meetings m WHERE m.project_id = p.id) as meeting_count
            FROM projects p
            WHERE p.user_id = ?
            ORDER BY p.updated_at DESC
        """, (user_id,))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_project(self, project_id: int) -> Optional[dict]:
        """Получение проекта по ID"""
        cursor = await self._conn.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_active_project(self, user_id: str) -> Optional[dict]:
        """Получение активного проекта пользователя"""
        cursor = await self._conn.execute("""
            SELECT p.*,
                   (SELECT COUNT(*) FROM meetings m WHERE m.project_id = p.id) as meeting_count
            FROM projects p
            WHERE p.user_id = ? AND p.active = 1
            ORDER BY p.updated_at DESC
            LIMIT 1
        """, (user_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_project_history(self, project_id: int) -> list:
        """Получение истории созвонов проекта"""
        cursor = await self._conn.execute("""
            SELECT version, analysis, created_at
            FROM meetings
            WHERE project_id = ?
            ORDER BY version ASC
        """, (project_id,))
        rows = await cursor.fetchall()

        history = []
        for row in rows:
            meeting = dict(row)
            if meeting['analysis']:
                try:
                    meeting['analysis'] = json.loads(meeting['analysis'])
                except (json.JSONDecodeError, TypeError):
                    pass
            history.append(meeting)

        return history

    async def save_meeting(self, project_id: int, text: str, analysis: dict, file_type: str = "text") -> dict:
        """Сохранение созвона"""
        # Получаем следующую версию
        cursor = await self._conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 as next_version FROM meetings WHERE project_id = ?",
            (project_id,)
        )
        row = await cursor.fetchone()
        version = row['next_version'] if row else 1

        # Сохраняем
        cursor = await self._conn.execute(
            "INSERT INTO meetings (project_id, version, text, analysis, file_type) VALUES (?, ?, ?, ?, ?)",
            (project_id, version, text, json.dumps(analysis, ensure_ascii=False), file_type)
        )
        await self._conn.commit()

        # Обновляем дату проекта
        await self._conn.execute(
            "UPDATE projects SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (project_id,)
        )
        await self._conn.commit()

        return {
            "id": cursor.lastrowid,
            "version": version,
            "project_id": project_id
        }

    async def _ensure_user(self, user_id: str, username: str = None):
        """Создание пользователя, если не существует"""
        cursor = await self._conn.execute(
            "SELECT id FROM users WHERE user_id = ?",
            (user_id,)
        )
        if not await cursor.fetchone():
            await self._conn.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            await self._conn.commit()

    async def close(self):
        """Закрытие соединения"""
        if self._conn:
            await self._conn.close()