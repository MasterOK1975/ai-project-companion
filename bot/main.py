@dp.message(ProjectStates.waiting_for_name)
async def process_project_name(message: Message, state: FSMContext):
    """Обработка введённого названия проекта"""
    # Если пользователь ввёл команду — выходим из состояния
    if message.text.startswith("/"):
        await state.clear()
        # Пробрасываем команду обратно в диспетчер
        await dp.feed_update(bot, Update(
            update_id=message.message_id,
            message=message
        ))
        return

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


@dp.message(TZStates.waiting_for_text)
async def process_tz_text(message: Message, state: FSMContext):
    """Обработка введённого текста ТЗ"""
    # Если пользователь ввёл команду — выходим из состояния
    if message.text.startswith("/"):
        await state.clear()
        await dp.feed_update(bot, Update(
            update_id=message.message_id,
            message=message
        ))
        return

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


@dp.message(ChatStates.waiting_for_text)
async def process_chat_text(message: Message, state: FSMContext):
    """Обработка введённого текста переписки"""
    # Если пользователь ввёл команду — выходим из состояния
    if message.text.startswith("/"):
        await state.clear()
        await dp.feed_update(bot, Update(
            update_id=message.message_id,
            message=message
        ))
        return

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