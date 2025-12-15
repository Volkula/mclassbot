from aiogram import Router, F
from aiogram.types import (
    Message,
    BufferedInputFile,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command, StateFilter
from database.models import User, UserRole, Event, EventStatus
from bot.keyboards.common_keyboards import get_main_menu_keyboard
from config import settings
from database.database import SessionLocal
from database.models import Event, Registration
from datetime import datetime
import io

router = Router()

# Хранилище режима просмотра (в продакшене лучше использовать Redis или БД)
user_view_mode = {}


@router.message(Command("start"))
async def cmd_start(message: Message, user: User):
    """Обработчик команды /start"""
    # Сбрасываем режим просмотра
    user_view_mode[user.telegram_id] = False
    
    welcome_text = f"Привет, {user.full_name or 'пользователь'}!\n\n"
    
    if user.role.value == "admin":
        welcome_text += "Вы вошли как администратор. У вас есть полный доступ ко всем функциям."
    elif user.role.value == "assistant":
        welcome_text += "Вы вошли как помощник. Вы можете управлять событиями, на которые у вас есть права."
    else:
        welcome_text += "Добро пожаловать! Вы можете просматривать события и регистрироваться на них прямо в боте."
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu_keyboard(user.role, view_as_user=False)
    )


@router.message(Command("events"))
async def cmd_events(message: Message, user: User):
    """
    Универсальная команда /events:
    - работает в личке, группах и супергруппах;
    - показывает только список доступных событий в пользовательском режиме,
      без управления регистрациями и админских меню.
    """
    db = SessionLocal()
    try:
        events = db.query(Event).filter(
            Event.status.in_([EventStatus.APPROVED, EventStatus.ACTIVE])
        ).order_by(Event.date_time.asc()).all()

        if not events:
            await message.answer("📅 Нет доступных событий.")
            return

        from utils.timezone import format_event_datetime

        lines = ["📅 Доступные события:\n"]
        for ev in events:
            lines.append(f"• {ev.title} — {format_event_datetime(ev.date_time)}")

        text = "\n".join(lines)
        await message.answer(text)
    finally:
        db.close()


@router.inline_query()
async def inline_events(query: InlineQuery):
    """
    Inline‑режим: @бот → список активных событий.
    Показывает карточки событий, по клику вставляется сообщение с описанием
    и кнопкой «Подробнее», которая ведёт в обычный user_event_detail.
    """
    db = SessionLocal()
    try:
        events = db.query(Event).filter(
            Event.status.in_([EventStatus.APPROVED, EventStatus.ACTIVE])
        ).order_by(Event.date_time.asc()).limit(20).all()

        if not events:
            await query.answer([], cache_time=5, is_personal=True)
            return

        from utils.timezone import format_event_datetime

        results = []
        for ev in events:
            title = ev.title
            date_str = format_event_datetime(ev.date_time)

            text_lines = [
                f"📅 {ev.title}",
                f"📆 {date_str}",
            ]
            if ev.description:
                text_lines.append("")
                text_lines.append(ev.description)

            content = InputTextMessageContent(
                message_text="\n".join(text_lines),
                disable_web_page_preview=True,
            )

            # Кнопка ведёт пользователя в личный чат с ботом
            # (по клику Telegram открывает бота).
            if settings.BOT_USERNAME:
                bot_url = f"https://t.me/{settings.BOT_USERNAME}"
            else:
                bot_url = "https://t.me"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="ℹ️ Подробнее в боте",
                    url=bot_url,
                )
            ]])

            results.append(
                InlineQueryResultArticle(
                    id=str(ev.id),
                    title=title,
                    description=date_str,
                    input_message_content=content,
                    reply_markup=keyboard,
                )
            )

        await query.answer(results, cache_time=5, is_personal=False)
    finally:
        db.close()


@router.message(F.text == "📅 События")
async def show_events(message: Message, user: User):
    """Показать события"""
    # Проверяем режим просмотра
    view_as_user = user_view_mode.get(user.telegram_id, False)
    
    if view_as_user or user.role.value == "user":
        # Режим просмотра от имени пользователя или обычный пользователь
        from bot.handlers.user_handlers import user_show_events
        await user_show_events(message, user)
    elif user.role.value == "admin":
        from bot.keyboards.admin_keyboards import get_admin_events_menu
        await message.answer("Управление событиями:", reply_markup=get_admin_events_menu())
    elif user.role.value == "assistant":
        from bot.keyboards.assistant_keyboards import get_assistant_events_menu
        await message.answer("Мои события:", reply_markup=get_assistant_events_menu())


@router.message(F.text == "📋 Регистрации")
async def show_registrations_menu(message: Message, user: User):
    """Показать меню регистраций"""
    view_as_user = user_view_mode.get(user.telegram_id, False)
    
    if view_as_user:
        await message.answer("Для просмотра регистраций используйте мини-приложение.")
    elif user.role.value == "admin":
        from bot.handlers.admin_handlers import admin_registrations_menu
        await admin_registrations_menu(message, user)
    elif user.role.value == "assistant":
        from bot.handlers.assistant_handlers import assistant_registrations_menu
        await assistant_registrations_menu(message, user)
    else:
        await message.answer("Для просмотра регистраций используйте мини-приложение.")


@router.message(F.text == "👤 Посмотреть от имени пользователя")
async def view_as_user(message: Message, user: User):
    """Переключиться в режим просмотра от имени пользователя"""
    if user.role.value not in ["admin", "assistant"]:
        await message.answer("Эта функция доступна только администраторам и помощникам.")
        return
    
    user_view_mode[user.telegram_id] = True
    await message.answer(
        "✅ Вы переключились в режим просмотра от имени пользователя.\n\n"
        "Теперь вы видите интерфейс как обычный пользователь.",
        reply_markup=get_main_menu_keyboard(user.role, view_as_user=True)
    )


@router.message(F.text == "🔙 Вернуться к админ-панели")
async def return_to_admin(message: Message, user: User):
    """Вернуться к админ-панели"""
    if user.role.value not in ["admin", "assistant"]:
        await message.answer("Эта функция доступна только администраторам и помощникам.")
        return
    
    user_view_mode[user.telegram_id] = False
    
    role_text = "администратора" if user.role.value == "admin" else "помощника"
    await message.answer(
        f"✅ Вы вернулись к панели {role_text}.",
        reply_markup=get_main_menu_keyboard(user.role, view_as_user=False)
    )


@router.message(F.text == "📧 Отправить отчет")
async def send_report(message: Message, user: User):
    """Отправить отчет о событиях и участниках"""
    if user.role.value != "admin":
        await message.answer("Эта функция доступна только администраторам.")
        return
    
    db = SessionLocal()
    try:
        # Получаем все события
        events = db.query(Event).order_by(Event.date_time.desc()).all()
        
        if not events:
            await message.answer("Нет событий для отчета.")
            return
        
        # Формируем отчет
        report_text = "📊 ОТЧЕТ О СОБЫТИЯХ И УЧАСТНИКАХ\n\n"
        from utils.timezone import get_local_now
        report_text += f"Дата формирования: {get_local_now().strftime('%d.%m.%Y %H:%M')}\n\n"
        
        total_registrations = 0
        active_events = 0
        
        for event in events:
            registrations_count = len(event.registrations)
            total_registrations += registrations_count
            
            if event.status.value in ["approved", "active"]:
                active_events += 1
            
            report_text += f"📅 {event.title}\n"
            from utils.timezone import format_event_datetime
            report_text += f"   Дата: {format_event_datetime(event.date_time)}\n"
            report_text += f"   Статус: {event.status.value}\n"
            report_text += f"   Регистраций: {registrations_count}\n\n"
        
        report_text += f"\n📈 СТАТИСТИКА:\n"
        report_text += f"Всего событий: {len(events)}\n"
        report_text += f"Активных событий: {active_events}\n"
        report_text += f"Всего регистраций: {total_registrations}\n"
        
        # Отправляем отчет
        await message.answer(report_text)
        
        # Также создаем CSV файл с детальной информацией
        csv_lines = ["Событие,Дата,Статус,Регистраций,Участники\n"]
        
        for event in events:
            event_title = event.title.replace(",", " ").replace("\n", " ")
            from utils.timezone import format_event_datetime
            event_date = format_event_datetime(event.date_time)
            event_status = event.status.value
            reg_count = len(event.registrations)
            
            # Список участников
            participants = []
            for reg in event.registrations[:10]:  # Первые 10 для CSV
                user_obj = db.query(User).filter(User.telegram_id == reg.user_telegram_id).first()
                if user_obj:
                    participants.append(user_obj.full_name or f"ID:{reg.user_telegram_id}")
            
            participants_str = "; ".join(participants)
            if len(event.registrations) > 10:
                participants_str += f" и еще {len(event.registrations) - 10}"
            
            csv_lines.append(f"{event_title},{event_date},{event_status},{reg_count},{participants_str}\n")
        
        csv_content = "".join(csv_lines)
        csv_bytes = csv_content.encode('utf-8')
        from utils.timezone import get_local_now
        filename = f"report_{get_local_now().strftime('%Y%m%d_%H%M%S')}.csv"

        csv_file = BufferedInputFile(csv_bytes, filename=filename)
        await message.answer_document(csv_file, caption="📊 Детальный отчет в формате CSV")
        
    finally:
        db.close()

