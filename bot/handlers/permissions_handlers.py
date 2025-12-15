from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import User, Event, UserRole, UserEventPermission
from utils.permissions import is_admin
from database.database import SessionLocal
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


class AssignPermissionStates(StatesGroup):
    waiting_user = State()
    waiting_permissions = State()


@router.callback_query(F.data.startswith("admin_permissions_"))
async def admin_permissions_menu(callback: CallbackQuery, user: User):
    """Меню управления правами на событие"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        # Получаем текущие права
        permissions = db.query(UserEventPermission).filter(
            UserEventPermission.event_id == event_id
        ).all()
        
        text = f"👥 Права доступа к событию: {event.title}\n\n"
        
        if permissions:
            text += "Текущие права:\n"
            for perm in permissions:
                perm_user = db.query(User).filter(User.id == perm.user_id).first()
                if perm_user:
                    text += f"• {perm_user.full_name or 'Без имени'}\n"
                    text += f"  ✏️ Редактирование: {'✅' if perm.can_edit else '❌'}\n"
                    text += f"  👁️ Просмотр регистраций: {'✅' if perm.can_view_registrations else '❌'}\n"
                    text += f"  🔔 Уведомления: {'✅' if perm.can_send_notifications else '❌'}\n\n"
        else:
            text += "Права не назначены.\n\n"
        
        keyboard = [
            [InlineKeyboardButton(text="➕ Назначить права", callback_data=f"admin_assign_permission_{event_id}")],
            [InlineKeyboardButton(text="📋 Список помощников", callback_data=f"admin_list_assistants_{event_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_event_{event_id}")],
        ]
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_assign_permission_"))
async def admin_assign_permission_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало назначения прав"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        # Получаем список помощников
        assistants = db.query(User).filter(User.role == UserRole.ASSISTANT).all()
        
        if not assistants:
            await callback.message.answer("Нет помощников. Сначала назначьте роль помощника пользователю.")
            await callback.answer()
            return
        
        await state.update_data(event_id=event_id)
        
        text = "Выберите помощника для назначения прав:\n\n"
        keyboard = []
        for assistant in assistants:
            text += f"• {assistant.full_name or 'Без имени'} (ID: {assistant.telegram_id})\n"
            keyboard.append([InlineKeyboardButton(
                text=f"👤 {assistant.full_name or 'Без имени'}",
                callback_data=f"admin_select_assistant_{event_id}_{assistant.id}"
            )])
        
        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_permissions_{event_id}")])
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_select_assistant_"))
async def admin_select_assistant(callback: CallbackQuery, user: User):
    """Выбор помощника для назначения прав"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    event_id = int(parts[-2])
    assistant_id = int(parts[-1])
    
    db = SessionLocal()
    try:
        assistant = db.query(User).filter(User.id == assistant_id).first()
        event = db.query(Event).filter(Event.id == event_id).first()
        
        if not assistant or not event:
            await callback.answer("Ошибка: пользователь или событие не найдены.", show_alert=True)
            return
        
        # Проверяем, есть ли уже права
        existing = db.query(UserEventPermission).filter(
            UserEventPermission.user_id == assistant_id,
            UserEventPermission.event_id == event_id
        ).first()
        
        if existing:
            # Редактируем существующие права
            text = f"Редактирование прав для: {assistant.full_name or 'Без имени'}\n"
            text += f"Событие: {event.title}\n\n"
            text += "Текущие права:\n"
            text += f"✏️ Редактирование: {'✅' if existing.can_edit else '❌'}\n"
            text += f"👁️ Просмотр регистраций: {'✅' if existing.can_view_registrations else '❌'}\n"
            text += f"🔔 Уведомления: {'✅' if existing.can_send_notifications else '❌'}\n\n"
            text += "Выберите права:"
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text=f"{'✅' if existing.can_edit else '❌'} Редактирование",
                        callback_data=f"admin_toggle_edit_{event_id}_{assistant_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{'✅' if existing.can_view_registrations else '❌'} Просмотр регистраций",
                        callback_data=f"admin_toggle_view_{event_id}_{assistant_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text=f"{'✅' if existing.can_send_notifications else '❌'} Уведомления",
                        callback_data=f"admin_toggle_notify_{event_id}_{assistant_id}"
                    )
                ],
                [InlineKeyboardButton(text="🗑️ Удалить права", callback_data=f"admin_remove_permission_{event_id}_{assistant_id}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_permissions_{event_id}")],
            ]
        else:
            # Создаем новые права
            text = f"Назначение прав для: {assistant.full_name or 'Без имени'}\n"
            text += f"Событие: {event.title}\n\n"
            text += "Выберите права (по умолчанию все включены):"
            
            keyboard = [
                [
                    InlineKeyboardButton(
                        text="✅ Редактирование",
                        callback_data=f"admin_toggle_edit_{event_id}_{assistant_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Просмотр регистраций",
                        callback_data=f"admin_toggle_view_{event_id}_{assistant_id}"
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="✅ Уведомления",
                        callback_data=f"admin_toggle_notify_{event_id}_{assistant_id}"
                    )
                ],
                [InlineKeyboardButton(text="💾 Сохранить", callback_data=f"admin_save_permission_{event_id}_{assistant_id}")],
                [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_assign_permission_{event_id}")],
            ]
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_toggle_edit_"))
async def admin_toggle_edit(callback: CallbackQuery, user: User):
    """Переключение права на редактирование"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    event_id = int(parts[-2])
    assistant_id = int(parts[-1])
    
    db = SessionLocal()
    try:
        perm = db.query(UserEventPermission).filter(
            UserEventPermission.user_id == assistant_id,
            UserEventPermission.event_id == event_id
        ).first()
        
        if perm:
            perm.can_edit = not perm.can_edit
        else:
            perm = UserEventPermission(
                user_id=assistant_id,
                event_id=event_id,
                can_edit=True,
                can_view_registrations=True,
                can_send_notifications=True
            )
            db.add(perm)
        
        db.commit()
        await admin_select_assistant(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_toggle_view_"))
async def admin_toggle_view(callback: CallbackQuery, user: User):
    """Переключение права на просмотр"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    event_id = int(parts[-2])
    assistant_id = int(parts[-1])
    
    db = SessionLocal()
    try:
        perm = db.query(UserEventPermission).filter(
            UserEventPermission.user_id == assistant_id,
            UserEventPermission.event_id == event_id
        ).first()
        
        if perm:
            perm.can_view_registrations = not perm.can_view_registrations
        else:
            perm = UserEventPermission(
                user_id=assistant_id,
                event_id=event_id,
                can_edit=True,
                can_view_registrations=True,
                can_send_notifications=True
            )
            db.add(perm)
        
        db.commit()
        await admin_select_assistant(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_toggle_notify_"))
async def admin_toggle_notify(callback: CallbackQuery, user: User):
    """Переключение права на уведомления"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    event_id = int(parts[-2])
    assistant_id = int(parts[-1])
    
    db = SessionLocal()
    try:
        perm = db.query(UserEventPermission).filter(
            UserEventPermission.user_id == assistant_id,
            UserEventPermission.event_id == event_id
        ).first()
        
        if perm:
            perm.can_send_notifications = not perm.can_send_notifications
        else:
            perm = UserEventPermission(
                user_id=assistant_id,
                event_id=event_id,
                can_edit=True,
                can_view_registrations=True,
                can_send_notifications=True
            )
            db.add(perm)
        
        db.commit()
        await admin_select_assistant(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_save_permission_"))
async def admin_save_permission(callback: CallbackQuery, user: User):
    """Сохранение прав"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    event_id = int(parts[-2])
    assistant_id = int(parts[-1])
    
    db = SessionLocal()
    try:
        perm = db.query(UserEventPermission).filter(
            UserEventPermission.user_id == assistant_id,
            UserEventPermission.event_id == event_id
        ).first()
        
        if not perm:
            perm = UserEventPermission(
                user_id=assistant_id,
                event_id=event_id,
                can_edit=True,
                can_view_registrations=True,
                can_send_notifications=True
            )
            db.add(perm)
        
        db.commit()
        await callback.answer("✅ Права сохранены!", show_alert=True)
        await admin_permissions_menu(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_remove_permission_"))
async def admin_remove_permission(callback: CallbackQuery, user: User):
    """Удаление прав"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    event_id = int(parts[-2])
    assistant_id = int(parts[-1])
    
    db = SessionLocal()
    try:
        perm = db.query(UserEventPermission).filter(
            UserEventPermission.user_id == assistant_id,
            UserEventPermission.event_id == event_id
        ).first()
        
        if perm:
            db.delete(perm)
            db.commit()
            await callback.answer("✅ Права удалены!", show_alert=True)
        else:
            await callback.answer("Права не найдены.", show_alert=True)
        
        await admin_permissions_menu(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_list_assistants_"))
async def admin_list_assistants(callback: CallbackQuery, user: User):
    """Список помощников для назначения прав"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        assistants = db.query(User).filter(User.role == UserRole.ASSISTANT).all()
        
        if not assistants:
            await callback.message.answer("Нет помощников.")
            await callback.answer()
            return
        
        text = "👥 Помощники:\n\n"
        for assistant in assistants:
            text += f"• {assistant.full_name or 'Без имени'}\n"
            text += f"  ID: {assistant.telegram_id}\n\n"
        
        keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_permissions_{event_id}")]]
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()
    finally:
        db.close()

