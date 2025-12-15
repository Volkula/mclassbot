from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command, StateFilter
from database.models import User, UserRole
from bot.keyboards.common_keyboards import get_main_menu_keyboard
from config import settings
from database.database import SessionLocal
from database.models import Event, Registration
from datetime import datetime
import io

router = Router()

# Хранилище режима просмотра (в продакшене лучше использовать Redis или БД)
user_view_mode = {}

# Хранилище последних ответов о недоступности переписки (по дням)
last_contact_reply = {}


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
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        from utils.timezone import get_local_now
        csv_file.name = f"report_{get_local_now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        await message.answer_document(
            csv_file,
            caption="📊 Детальный отчет в формате CSV"
        )
        
    finally:
        db.close()


@router.message(
    StateFilter(None),
    F.text
)
async def handle_free_text_message(message: Message, user: User, state):
    """
    Ответ пользователю, который пытается писать текстом организаторам.
    Срабатывает только когда нет активного состояния FSM и не нажаты
    стандартные кнопки меню. Не чаще одного раза в сутки на пользователя.
    """
    # Для админа и помощника не вмешиваемся — у них много пунктов меню и текстовых сценариев
    if user.role in {UserRole.ADMIN, UserRole.ASSISTANT}:
        return
    # Игнорируем команды
    if message.text.startswith("/"):
        return

    # Игнорируем стандартные кнопки меню, которые уже обрабатываются выше
    ignore_texts = {
        "📅 События",
        "📋 Регистрации",
        "📊 Регистрации",
        "📅 Мои события",
        "👤 Посмотреть от имени пользователя",
        "🔙 Вернуться к админ-панели",
        "📧 Отправить отчет",
        "⚙️ Настройки",
        "👥 Пользователи",
        "🔔 Уведомления",
    }
    if message.text in ignore_texts:
        return

    from utils.timezone import get_local_now

    today = get_local_now().date()
    last_date = last_contact_reply.get(user.telegram_id)

    # Уже отвечали сегодня — ничего не делаем
    if last_date == today:
        return

    # Запоминаем дату ответа и отправляем сообщение
    last_contact_reply[user.telegram_id] = today
    await message.answer("В этом боте пока недоступна функция переписки с организаторами.")

