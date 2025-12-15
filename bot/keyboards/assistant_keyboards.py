from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import EventStatus


def get_assistant_events_menu():
    """Меню событий для помощника"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Создать черновик", callback_data="assistant_create_draft")],
        [InlineKeyboardButton(text="📋 Мои события", callback_data="assistant_list_events")],
        [InlineKeyboardButton(text="📝 Мои черновики", callback_data="assistant_drafts")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_assistant_event_actions_keyboard(event_id: int, can_edit: bool):
    """Действия с событием для помощника"""
    keyboard = []
    
    if can_edit:
        keyboard.append([InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"assistant_edit_{event_id}")])
    
    keyboard.extend([
        [InlineKeyboardButton(text="📊 Регистрации", callback_data=f"assistant_registrations_{event_id}")],
        [InlineKeyboardButton(text="🔔 Отправить уведомление", callback_data=f"assistant_send_notification_{event_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="assistant_events_menu")],
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

