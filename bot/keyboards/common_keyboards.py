from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from database.models import UserRole


def get_main_menu_keyboard(user_role: UserRole, view_as_user: bool = False):
    """Главное меню в зависимости от роли"""
    buttons = []
    
    if view_as_user:
        # Режим просмотра от имени пользователя
        buttons = [
            [KeyboardButton(text="📅 События")],
            [KeyboardButton(text="🔙 Вернуться к админ-панели")],
        ]
    elif user_role == UserRole.ADMIN:
        buttons = [
            [KeyboardButton(text="📅 События")],
            [KeyboardButton(text="👥 Пользователи")],
            [KeyboardButton(text="📊 Регистрации")],
            [KeyboardButton(text="🔔 Уведомления")],
            [KeyboardButton(text="⚙️ Настройки")],
            [KeyboardButton(text="👤 Посмотреть от имени пользователя")],
            [KeyboardButton(text="📧 Отправить отчет")],
        ]
    elif user_role == UserRole.ASSISTANT:
        buttons = [
            [KeyboardButton(text="📅 Мои события")],
            [KeyboardButton(text="📊 Регистрации")],
            [KeyboardButton(text="🔔 Уведомления")],
            [KeyboardButton(text="👤 Посмотреть от имени пользователя")],
        ]
    else:
        buttons = [
            [KeyboardButton(text="📅 События")],
        ]
    
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_events_list_keyboard(events, prefix="event"):
    """Клавиатура со списком событий"""
    from utils.timezone import format_event_datetime
    
    keyboard = []
    for event in events:
        keyboard.append([InlineKeyboardButton(
            text=f"{event.title} ({format_event_datetime(event.date_time)})",
            callback_data=f"{prefix}_{event.id}"
        )])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_back_keyboard(callback_data="back"):
    """Кнопка назад"""
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Назад", callback_data=callback_data)
    ]])

