from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.models import EventStatus


def get_admin_events_menu():
    """Меню управления событиями для админа"""
    keyboard = [
        [InlineKeyboardButton(text="➕ Создать событие", callback_data="admin_create_event")],
        [InlineKeyboardButton(text="📋 Все события", callback_data="admin_list_events")],
        [InlineKeyboardButton(text="📝 Черновики", callback_data="admin_drafts")],
        [InlineKeyboardButton(text="✅ На утверждение", callback_data="admin_pending_approval")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_event_actions_keyboard(event_id: int, status: EventStatus):
    """Действия с событием"""
    keyboard = []
    
    if status == EventStatus.DRAFT:
        keyboard.append([InlineKeyboardButton(text="✅ Утвердить", callback_data=f"admin_approve_{event_id}")])
    
    keyboard.extend([
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_edit_{event_id}")],
        [InlineKeyboardButton(text="📷 Изменить фото", callback_data=f"admin_edit_photo_{event_id}")],
        [InlineKeyboardButton(text="👥 Лимит участников", callback_data=f"admin_edit_max_participants_{event_id}")],
        [InlineKeyboardButton(text="📊 Регистрации", callback_data=f"admin_registrations_{event_id}")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data=f"admin_notifications_{event_id}")],
        [InlineKeyboardButton(text="👥 Права доступа", callback_data=f"admin_permissions_{event_id}")],
    ])
    
    if status != EventStatus.ARCHIVED:
        keyboard.append([InlineKeyboardButton(text="🗄️ Архивировать", callback_data=f"admin_archive_{event_id}")])
    else:
        keyboard.append([InlineKeyboardButton(text="📤 Разархивировать", callback_data=f"admin_unarchive_{event_id}")])
    
    keyboard.append([InlineKeyboardButton(text="🗑️ Удалить событие", callback_data=f"admin_delete_event_{event_id}")])
    keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_events_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_users_menu_keyboard():
    """Меню управления пользователями"""
    keyboard = [
        [InlineKeyboardButton(text="👥 Список пользователей", callback_data="admin_list_users")],
        [InlineKeyboardButton(text="➕ Назначить помощника", callback_data="admin_add_assistant")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_actions_keyboard(user_id: int):
    """Действия с пользователем"""
    keyboard = [
        [InlineKeyboardButton(text="👤 Изменить роль", callback_data=f"admin_change_role_{user_id}")],
        [InlineKeyboardButton(text="📊 Регистрации пользователя", callback_data=f"admin_user_registrations_{user_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_role_selection_keyboard(user_id: int):
    """Выбор роли для пользователя"""
    keyboard = [
        [InlineKeyboardButton(text="👑 Админ", callback_data=f"admin_set_role_{user_id}_admin")],
        [InlineKeyboardButton(text="👤 Помощник", callback_data=f"admin_set_role_{user_id}_assistant")],
        [InlineKeyboardButton(text="👥 Пользователь", callback_data=f"admin_set_role_{user_id}_user")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_user_{user_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_export_format_keyboard(event_id: int):
    """Выбор формата экспорта"""
    keyboard = [
        [InlineKeyboardButton(text="📄 CSV", callback_data=f"admin_export_csv_{event_id}")],
        [InlineKeyboardButton(text="📊 Excel", callback_data=f"admin_export_excel_{event_id}")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_event_{event_id}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

