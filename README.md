# 🧠 AI Project Companion

**AI-помощник по ведению проектов.**

Загрузи аудио, видео или текст созвона — получи полную расшифровку, саммари, список задач и историю проекта. Никаких споров, кто что обещал.

---

## 🚀 Возможности

- 🎙 **Расшифровка аудио/видео** — распознавание речи через Whisper
- 📝 **Краткое саммари** — о чём говорили, ёмко и по делу
- ✅ **Список задач** — что делает исполнитель, что делает заказчик
- 🔄 **Что изменилось** — автоматическое отслеживание изменений
- ⚠️ **Новый объём работ** — AI сам определит, что требует пересогласования
- 📊 **История проекта** — каждый созвон — новая версия
- ⚖️ **AI Arbitration** — независимая память проекта
- 🎯 **Scope Control** — контроль объёма работ

## 📋 Структура проекта

```
ai-project-companion/
├── bot/                  # Telegram-бот
│   ├── __init__.py
│   └── main.py          # Основной файл бота
├── core/                 # AI-логика
│   ├── analyzer.py      # Анализ созвонов через AI
│   └── transcriber.py   # Распознавание речи
├── db/                   # База данных
│   └── database.py      # Работа с БД (SQLite/PostgreSQL)
├── docs/                 # Документация
├── .env.example          # Пример переменных окружения
├── docker-compose.yml    # Docker Compose для продакшена
├── Dockerfile            # Docker-образ
├── requirements.txt      # Python-зависимости
└── README.md
```

## 🛠 Быстрый старт

### 1. Регистрация бота в Telegram

1. Открой [BotFather](https://t.me/BotFather)
2. Отправь `/newbot`
3. Задай имя и username бота
4. Сохрани полученный токен

### 2. Регистрация OpenRouter

1. Зайди на [openrouter.ai](https://openrouter.ai)
2. Зарегистрируйся
3. Пополни баланс (от $5)
4. Создай API-ключ

### 3. Настройка

```bash
# Клонируй репозиторий
git clone https://github.com/my-happy-life-rezanov/ai-project-companion.git
cd ai-project-companion

# Скопируй и заполни .env
cp .env.example .env
# Отредактируй .env: вставь BOT_TOKEN и OPENROUTER_API_KEY
```

### 4. Запуск

**Локально:**
```bash
pip install -r requirements.txt
python -m bot.main
```

**Через Docker:**
```bash
docker-compose up -d
```

## 🤖 Команды Telegram-бота

| Команда | Описание |
|---|---|
| `/start` | Приветствие и инструкция |
| `/help` | Подробная справка |
| `/new_project Название` | Создать новый проект |
| `/projects` | Список проектов |
| `/select_project ID` | Выбрать проект |

## 🧠 AI-модели

По умолчанию используется **GPT-4o** через OpenRouter. Можно сменить модель в `.env`:

```
AI_MODEL=openai/gpt-4o        # GPT-4o (рекомендуется)
AI_MODEL=anthropic/claude-3.5-sonnet  # Claude 3.5 Sonnet
AI_MODEL=google/gemini-pro    # Gemini Pro
AI_MODEL=openai/gpt-3.5-turbo # GPT-3.5 Turbo (дешевле)
```

## ☁️ Деплой

### Через SourceCraft (рекомендуется для MVP)

1. Создай сервисное подключение к Yandex Cloud
2. Настрой CI/CD в `.sourcecraft/ci.yaml`
3. Запусти workflow

### На собственном сервере

```bash
# Установи Docker и Docker Compose
# Скопируй файлы проекта на сервер
# Запусти
docker-compose up -d
```

### Локально

```bash
python -m bot.main
```

## 💰 Билинг

- **OpenRouter** — оплата за токены AI-моделей (~$0.05-0.10 за созвон)
- **Whisper** — $0.006 за минуту аудио (или бесплатно через локальную модель)
- **Сервер** — от 300 руб/мес (Yandex Cloud / VPS)

## 📄 Лицензия

MIT