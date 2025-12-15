from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import User, Event, EventStatus, UserRole, Registration, EventField, FieldType, EventNotification, NotificationTemplate, UserEventPermission, ScheduledNotification
from bot.handlers.event_management import EditEventStates
from bot.keyboards.admin_keyboards import (
    get_admin_events_menu,
    get_event_actions_keyboard,
    get_users_menu_keyboard,
    get_user_actions_keyboard,
    get_role_selection_keyboard,
    get_export_format_keyboard
)
from utils.permissions import is_admin
from utils.export import export_registrations_to_csv, export_registrations_to_excel
from datetime import datetime
import io
from database.database import SessionLocal

router = Router()


class CreateEventStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_date = State()
    waiting_photo = State()
    waiting_max_participants = State()
    waiting_fields = State()


class AddNotificationStates(StatesGroup):
    waiting_custom_time = State()


@router.message(F.text == "👥 Пользователи")
async def admin_users_menu(message: Message, user: User):
    """Меню управления пользователями"""
    if not is_admin(user):
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    await message.answer("Управление пользователями:", reply_markup=get_users_menu_keyboard())


@router.message(F.text == "📊 Регистрации")
async def admin_registrations_menu(message: Message, user: User):
    """Меню регистраций"""
    if not is_admin(user):
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    from database.database import SessionLocal
    from bot.keyboards.common_keyboards import get_events_list_keyboard
    
    db = SessionLocal()
    try:
        events = db.query(Event).filter(Event.status.in_([EventStatus.APPROVED, EventStatus.ACTIVE])).all()
        if not events:
            await message.answer("Нет активных событий.")
            return
        
        await message.answer(
            "Выберите событие для просмотра регистраций:",
            reply_markup=get_events_list_keyboard(events, "admin_registrations")
        )
    finally:
        db.close()


@router.message(F.text == "🔔 Уведомления")
async def admin_notifications_menu(message: Message, user: User):
    """Меню уведомлений"""
    if not is_admin(user):
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    from database.database import SessionLocal
    from bot.keyboards.common_keyboards import get_events_list_keyboard
    
    db = SessionLocal()
    try:
        events = db.query(Event).filter(Event.status.in_([EventStatus.APPROVED, EventStatus.ACTIVE])).all()
        if not events:
            await message.answer("Нет активных событий для настройки уведомлений.")
            return
        
        await message.answer(
            "Выберите событие для настройки уведомлений:",
            reply_markup=get_events_list_keyboard(events, "admin_notifications")
        )
    finally:
        db.close()


@router.message(F.text == "⚙️ Настройки")
async def admin_settings_menu(message: Message, user: User):
    """Меню настроек"""
    if not is_admin(user):
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    from bot.handlers.settings_handlers import admin_settings_menu as settings_menu
    await settings_menu(message, user)


@router.callback_query(F.data == "admin_events_menu")
async def admin_events_menu_callback(callback: CallbackQuery, user: User):
    """Меню событий для админа"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    try:
        await callback.message.edit_text("Управление событиями:", reply_markup=get_admin_events_menu())
    except:
        # Если сообщение с фото, отправляем новое
        await callback.message.answer("Управление событиями:", reply_markup=get_admin_events_menu())
        try:
            await callback.message.delete()
        except:
            pass
    await callback.answer()


@router.callback_query(F.data == "admin_list_events")
async def admin_list_events_callback(callback: CallbackQuery, user: User):
    """Список всех событий"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    from database.database import SessionLocal
    from bot.keyboards.common_keyboards import get_events_list_keyboard
    
    db = SessionLocal()
    try:
        events = db.query(Event).order_by(Event.date_time.desc()).limit(20).all()
        if not events:
            await callback.message.edit_text("Нет событий.")
            return
        
        await callback.message.edit_text(
            "Выберите событие:",
            reply_markup=get_events_list_keyboard(events, "admin_event")
        )
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_event_"))
async def admin_event_detail(callback: CallbackQuery, user: User):
    """Детали события для админа"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    from database.database import SessionLocal
    
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        status_emoji = "⚠️ " if event.status == EventStatus.ARCHIVED else ""
        text = f"{status_emoji}📅 {event.title}\n\n"
        text += f"📝 Описание: {event.description or 'Нет описания'}\n"
        from utils.timezone import format_event_datetime
        text += f"📆 Дата: {format_event_datetime(event.date_time)}\n"
        text += f"📊 Статус: {event.status.value}\n"
        text += f"👤 Создано: {event.creator.full_name or 'Неизвестно'}\n"
        
        registrations_count = len(event.registrations)
        text += f"📋 Регистраций: {registrations_count}"
        if event.max_participants:
            text += f" / {event.max_participants} (лимит)"
            if registrations_count >= event.max_participants:
                text += " ⚠️ Лимит достигнут"
        
        # Отправляем фото, если есть
        if event.photo_file_id:
            try:
                await callback.message.answer_photo(
                    photo=event.photo_file_id,
                    caption=text,
                    reply_markup=get_event_actions_keyboard(event.id, event.status)
                )
                # Пытаемся удалить старое сообщение, если это возможно
                try:
                    await callback.message.delete()
                except:
                    pass
                await callback.answer()
                return
            except Exception:
                # Если фото не удалось отправить, отправляем текст
                pass
        
        try:
            await callback.message.edit_text(text, reply_markup=get_event_actions_keyboard(event.id, event.status))
        except:
            # Если сообщение с фото, отправляем новое
            await callback.message.answer(text, reply_markup=get_event_actions_keyboard(event.id, event.status))
            try:
                await callback.message.delete()
            except:
                pass
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_notifications_"))
async def admin_event_notifications(callback: CallbackQuery, user: User):
    """Настройка уведомлений для события"""
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
        
        from database.models import EventNotification, NotificationTemplate, UserEventPermission
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        notifications = db.query(EventNotification).filter(EventNotification.event_id == event_id).all()
        templates = db.query(NotificationTemplate).all()
        
        text = f"🔔 Уведомления для события: {event.title}\n\n"
        
        keyboard = []
        if notifications:
            text += "Текущие настройки уведомлений:\n"
            for notif in notifications:
                line = "• "
                if notif.template_id:
                    template = db.query(NotificationTemplate).filter(NotificationTemplate.id == notif.template_id).first()
                    if template:
                        if template.absolute_datetime:
                            line += f"Шаблон: {template.name} ({template.absolute_datetime.strftime('%d.%m.%Y %H:%M')})"
                        elif template.time_before_event:
                            days = template.time_before_event // (24 * 60)
                            hours = (template.time_before_event % (24 * 60)) // 60
                            if days > 0:
                                line += f"Шаблон: {template.name} (за {days} дн. {hours} ч.)"
                            else:
                                line += f"Шаблон: {template.name} (за {template.time_before_event} мин.)"
                        else:
                            line += f"Шаблон: {template.name}"
                    else:
                        line += "Шаблон: (не найден)"
                elif notif.custom_time:
                    line += f"Кастомное время: за {notif.custom_time} минут"
                else:
                    line += "Без времени"
                
                text += line + "\n"
                text += f"  Статус: {'✅ Включено' if notif.enabled else '❌ Выключено'}\n"
                text += f"  Кнопки: {'✅ Включены' if notif.include_buttons else '❌ Выключены'}\n"
                
                # Показываем получателей
                if notif.notification_recipients:
                    recipients = db.query(User).filter(User.id.in_(notif.notification_recipients)).all()
                    if recipients:
                        text += f"  Получатели: {', '.join([r.full_name or f'ID:{r.id}' for r in recipients])}\n"
                else:
                    text += f"  Получатели: По умолчанию (автор + помощники)\n"
                text += "\n"

                # Кнопка удаления конкретного уведомления
                keyboard.append([
                    InlineKeyboardButton(
                        text=f"🗑️ Удалить уведомление #{notif.id}",
                        callback_data=f"admin_delete_notification_{notif.id}"
                    )
                ])
        else:
            text += "Уведомления не настроены.\n\n"

        # Показать запланированные уведомления (ScheduledNotification)
        from utils.timezone import utc_to_local
        scheduled = db.query(ScheduledNotification).filter(
            ScheduledNotification.event_id == event_id
        ).order_by(ScheduledNotification.scheduled_time.asc()).all()

        text += "------------------------\n"
        if scheduled:
            total = len(scheduled)
            sent = sum(1 for s in scheduled if s.sent)
            text += f"📆 Запланированные отправки: всего {total}, отправлено {sent}\n"
            
            for s in scheduled[:10]:
                local_dt = utc_to_local(s.scheduled_time)
                status = "✅ отправлено" if s.sent else "⏳ запланировано"
                text += f"• Регистрация #{s.registration_id}: {local_dt.strftime('%d.%m.%Y %H:%M')} ({status})\n"
            if total > 10:
                text += f"... и еще {total - 10} уведомлений\n"
            text += "\n"
        else:
            text += "Запланированные уведомления отсутствуют.\n\n"
        
        # Нижнее меню
        keyboard.append([
            InlineKeyboardButton(text="➕ Добавить уведомление", callback_data=f"admin_add_notification_{event_id}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="⚙️ Получатели", callback_data=f"admin_notification_recipients_{event_id}")
        ])
        keyboard.append([
            InlineKeyboardButton(text="📋 Шаблоны уведомлений", callback_data="settings_templates")
        ])
        keyboard.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_event_{event_id}")
        ])
        
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        except:
            # Если сообщение с фото, отправляем новое
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
            try:
                await callback.message.delete()
            except:
                pass
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_notification_recipients_"))
async def admin_notification_recipients(callback: CallbackQuery, user: User):
    """Настройка получателей уведомлений"""
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
        
        from database.models import EventNotification, UserEventPermission, UserRole
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Получаем или создаем настройки уведомлений
        event_notif = db.query(EventNotification).filter(EventNotification.event_id == event_id).first()
        if not event_notif:
            event_notif = EventNotification(
                event_id=event_id,
                enabled=True,
                include_buttons=True
            )
            db.add(event_notif)
            db.commit()
            db.refresh(event_notif)
        
        # Получаем список доступных получателей
        # Автор события
        creator = db.query(User).filter(User.id == event.created_by).first()
        
        # Помощники с правами на событие
        permissions = db.query(UserEventPermission).filter(
            UserEventPermission.event_id == event_id,
            UserEventPermission.can_send_notifications == True
        ).all()
        assistants = [db.query(User).filter(User.id == p.user_id).first() for p in permissions]
        assistants = [a for a in assistants if a]
        
        # Все админы
        all_admins = db.query(User).filter(User.role == UserRole.ADMIN).all()
        
        text = f"👥 Получатели уведомлений для события: {event.title}\n\n"
        
        current_recipients = event_notif.notification_recipients or []
        if current_recipients:
            recipients = db.query(User).filter(User.id.in_(current_recipients)).all()
            text += "Текущие получатели:\n"
            for r in recipients:
                text += f"• {r.full_name or 'Без имени'} ({r.role.value})\n"
        else:
            text += "Используются настройки по умолчанию:\n"
            if creator:
                text += f"• {creator.full_name or 'Без имени'} (автор события)\n"
            for a in assistants:
                text += f"• {a.full_name or 'Без имени'} (помощник)\n"
        
        text += "\nВыберите получателей:"
        
        keyboard = []
        
        # Автор события
        if creator:
            is_selected = creator.id in current_recipients if current_recipients else True
            keyboard.append([InlineKeyboardButton(
                text=f"{'✅' if is_selected else '❌'} Автор: {creator.full_name or 'Без имени'}",
                callback_data=f"admin_toggle_recipient_{event_id}_{creator.id}"
            )])
        
        # Помощники
        for assistant in assistants:
            is_selected = assistant.id in current_recipients if current_recipients else True
            keyboard.append([InlineKeyboardButton(
                text=f"{'✅' if is_selected else '❌'} Помощник: {assistant.full_name or 'Без имени'}",
                callback_data=f"admin_toggle_recipient_{event_id}_{assistant.id}"
            )])
        
        # Админы
        for admin in all_admins:
            is_selected = admin.id in current_recipients if current_recipients else False
            keyboard.append([InlineKeyboardButton(
                text=f"{'✅' if is_selected else '❌'} Админ: {admin.full_name or 'Без имени'}",
                callback_data=f"admin_toggle_recipient_{event_id}_{admin.id}"
            )])
        
        keyboard.append([InlineKeyboardButton(text="💾 Сохранить", callback_data=f"admin_save_recipients_{event_id}")])
        keyboard.append([InlineKeyboardButton(text="🔄 Сбросить к умолчанию", callback_data=f"admin_reset_recipients_{event_id}")])
        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_notifications_{event_id}")])
        
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        except Exception as e:
            # Игнорируем ошибку, если сообщение не изменилось
            if "message is not modified" not in str(e):
                raise
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_delete_notification_"))
async def admin_delete_notification(callback: CallbackQuery, user: User):
    """Удаление отдельного уведомления события"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    notif_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        from database.models import EventNotification
        notif = db.query(EventNotification).filter(EventNotification.id == notif_id).first()
        if not notif:
            await callback.answer("Уведомление не найдено.", show_alert=True)
            return
        
        event_id = notif.event_id
        db.delete(notif)
        db.commit()
        
        await callback.answer("✅ Уведомление удалено.", show_alert=True)
        # Обновляем экран настроек уведомлений для события
        from types import SimpleNamespace
        fake_callback = SimpleNamespace(
            data=f"admin_notifications_{event_id}",
            message=callback.message,
            answer=callback.answer
        )
        await admin_event_notifications(fake_callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_toggle_recipient_"))
async def admin_toggle_recipient(callback: CallbackQuery, user: User):
    """Переключение получателя уведомлений"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    event_id = int(parts[-2])
    recipient_id = int(parts[-1])
    
    db = SessionLocal()
    try:
        event_notif = db.query(EventNotification).filter(EventNotification.event_id == event_id).first()
        if not event_notif:
            event_notif = EventNotification(
                event_id=event_id,
                enabled=True,
                include_buttons=True
            )
            db.add(event_notif)
            db.commit()
            db.refresh(event_notif)
        
        current_recipients = event_notif.notification_recipients or []
        
        if recipient_id in current_recipients:
            current_recipients.remove(recipient_id)
        else:
            current_recipients.append(recipient_id)
        
        event_notif.notification_recipients = current_recipients
        db.commit()
        
        await admin_notification_recipients(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_save_recipients_"))
async def admin_save_recipients(callback: CallbackQuery, user: User):
    """Сохранение получателей"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        event_notif = db.query(EventNotification).filter(EventNotification.event_id == event_id).first()
        if event_notif:
            db.commit()
            await callback.answer("✅ Получатели сохранены!", show_alert=True)
        await admin_event_notifications(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_reset_recipients_"))
async def admin_reset_recipients(callback: CallbackQuery, user: User):
    """Сброс получателей к умолчанию"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        event_notif = db.query(EventNotification).filter(EventNotification.event_id == event_id).first()
        if event_notif:
            event_notif.notification_recipients = None  # None = использовать умолчания
            db.commit()
            await callback.answer("✅ Получатели сброшены к умолчанию!", show_alert=True)
        await admin_event_notifications(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_add_notification_"))
async def admin_add_notification_start(callback: CallbackQuery, user: User):
    """Начало добавления уведомления к событию"""
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
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        # Получаем список шаблонов
        templates = db.query(NotificationTemplate).all()
        
        if not templates:
            await callback.answer("Сначала создайте шаблон уведомления в настройках.", show_alert=True)
            return
        
        text = f"Выберите шаблон уведомления для события '{event.title}':\n\n"
        keyboard = []
        
        for template in templates:
            time_str = ""
            if template.absolute_datetime:
                time_str = f" ({template.absolute_datetime.strftime('%d.%m.%Y %H:%M')})"
            elif template.time_before_event:
                days = template.time_before_event // (24 * 60)
                hours = (template.time_before_event % (24 * 60)) // 60
                if days > 0:
                    time_str = f" (за {days} дн. {hours} ч.)"
                else:
                    time_str = f" (за {template.time_before_event} мин.)"
            
            keyboard.append([InlineKeyboardButton(
                text=f"📋 {template.name}{time_str}",
                callback_data=f"admin_use_template_{event_id}_{template.id}"
            )])
        
        keyboard.append([InlineKeyboardButton(text="⏰ Кастомное время", callback_data=f"admin_custom_notification_{event_id}")])
        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_notifications_{event_id}")])
        
        try:
            await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        except:
            await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
            try:
                await callback.message.delete()
            except:
                pass
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_use_template_"))
async def admin_use_template(callback: CallbackQuery, user: User):
    """Использование шаблона для уведомления"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    event_id = int(parts[-2])
    template_id = int(parts[-1])
    
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
        
        if not event or not template:
            await callback.answer("Событие или шаблон не найдены.", show_alert=True)
            return
        
        # Создаем или обновляем уведомление
        event_notif = db.query(EventNotification).filter(EventNotification.event_id == event_id).first()
        if not event_notif:
            event_notif = EventNotification(
                event_id=event_id,
                template_id=template_id,
                enabled=True,
                include_buttons=True
            )
            db.add(event_notif)
        else:
            event_notif.template_id = template_id
            event_notif.custom_time = None
        
        db.commit()
        
        # Создаем запланированные уведомления
        from services.notification_service import create_scheduled_notifications_for_event
        create_scheduled_notifications_for_event(db, event)
        
        await callback.answer("✅ Уведомление добавлено!", show_alert=True)
        await admin_event_notifications(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_custom_notification_"))
async def admin_custom_notification_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало добавления уведомления с кастомным временем"""
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
        
        await state.update_data(event_id=event_id)
        await callback.message.answer(
            f"Введите время уведомления в минутах до события '{event.title}':\n\n"
            "Например: 60 (за час), 1440 (за день), 4320 (за 3 дня)"
        )
        await state.set_state(AddNotificationStates.waiting_custom_time)
        await callback.answer()
    finally:
        db.close()


@router.message(AddNotificationStates.waiting_custom_time)
async def process_custom_notification_time(message: Message, state: FSMContext, user: User):
    """Обработка кастомного времени уведомления"""
    if not is_admin(user):
        await message.answer("У вас нет доступа.")
        await state.clear()
        return
    
    try:
        custom_time = int(message.text.strip())
        if custom_time <= 0:
            await message.answer("❌ Время должно быть положительным числом.")
            return
    except ValueError:
        await message.answer("❌ Введите число (минуты до события).")
        return
    
    data = await state.get_data()
    event_id = data['event_id']
    
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await message.answer("Событие не найдено.")
            await state.clear()
            return
        
        # Создаем или обновляем уведомление
        event_notif = db.query(EventNotification).filter(EventNotification.event_id == event_id).first()
        if not event_notif:
            event_notif = EventNotification(
                event_id=event_id,
                custom_time=custom_time,
                enabled=True,
                include_buttons=True
            )
            db.add(event_notif)
        else:
            event_notif.custom_time = custom_time
            event_notif.template_id = None
        
        db.commit()
        
        # Создаем запланированные уведомления
        from services.notification_service import create_scheduled_notifications_for_event
        create_scheduled_notifications_for_event(db, event)
        
        await message.answer(f"✅ Уведомление добавлено! Уведомление будет отправлено за {custom_time} минут до события.")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_edit_photo_"))
async def admin_edit_photo_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало редактирования фото события"""
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
        
        await state.update_data(event_id=event_id)
        await callback.message.answer("Отправьте новое фото для события:\n\n"
                                     "• Отправьте фото для замены\n"
                                     "• Отправьте '-' чтобы оставить текущее\n"
                                     "• Отправьте '--' чтобы удалить фото")
        await state.set_state(EditEventStates.waiting_photo)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_export_csv_"))
async def admin_export_csv(callback: CallbackQuery, user: User):
    """Экспорт в CSV"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    from database.database import SessionLocal
    
    db = SessionLocal()
    try:
        csv_data = export_registrations_to_csv(db, event_id)
        csv_bytes = csv_data.encode('utf-8')
        csv_file = BufferedInputFile(csv_bytes, filename=f"registrations_{event_id}.csv")
        
        await callback.message.answer_document(csv_file, caption="Экспорт регистраций в CSV")
        await callback.answer("Файл отправлен!")
    except Exception as e:
        error_msg = str(e)[:200]  # Ограничиваем длину сообщения
        await callback.answer(f"Ошибка: {error_msg}", show_alert=True)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_export_excel_"))
async def admin_export_excel(callback: CallbackQuery, user: User):
    """Экспорт в Excel"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        excel_data = export_registrations_to_excel(db, event_id)
        excel_file = BufferedInputFile(excel_data, filename=f"registrations_{event_id}.xlsx")
        
        await callback.message.answer_document(excel_file, caption="Экспорт регистраций в Excel")
        await callback.answer("Файл отправлен!")
    except Exception as e:
        error_msg = str(e)[:200]  # Ограничиваем длину сообщения
        await callback.answer(f"Ошибка: {error_msg}", show_alert=True)
    finally:
        db.close()


@router.callback_query(F.data == "admin_create_event")
async def admin_create_event_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало создания события"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    await callback.message.answer("Введите название события:")
    await state.set_state(CreateEventStates.waiting_title)
    await callback.answer()


@router.message(CreateEventStates.waiting_title)
async def process_event_title(message: Message, state: FSMContext):
    """Обработка названия события"""
    await state.update_data(title=message.text)
    await message.answer("Введите описание события (или отправьте '-' чтобы пропустить):")
    await state.set_state(CreateEventStates.waiting_description)


@router.message(CreateEventStates.waiting_description)
async def process_event_description(message: Message, state: FSMContext):
    """Обработка описания события"""
    description = message.text if message.text != "-" else None
    await state.update_data(description=description)
    await message.answer("Введите дату и время события в формате ДД.ММ.ГГГГ ЧЧ:ММ:")
    await state.set_state(CreateEventStates.waiting_date)


@router.message(CreateEventStates.waiting_date)
async def process_event_date(message: Message, state: FSMContext, user: User):
    """Обработка даты события"""
    try:
        from utils.timezone import parse_local_datetime
        date_str = message.text.strip()
        date_time = parse_local_datetime(date_str, "%d.%m.%Y %H:%M")
        
        await state.update_data(date_time=date_time)
        await message.answer("Отправьте фото для события (или отправьте '-' чтобы пропустить):")
        await state.set_state(CreateEventStates.waiting_photo)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
                           "Например: 25.12.2024 18:00")


@router.message(CreateEventStates.waiting_photo)
async def process_event_photo(message: Message, state: FSMContext, user: User):
    """Обработка фото события"""
    photo_file_id = None
    photo_file_ids = []
    
    if message.text and message.text.strip() == "-":
        # Пропускаем фото
        pass
    elif message.photo:
        # Получаем самое большое фото
        photo = message.photo[-1]
        photo_file_id = photo.file_id
        photo_file_ids = [photo_file_id]
    
    await state.update_data(photo_file_id=photo_file_id, photo_file_ids=photo_file_ids)
    await message.answer("Введите максимальное количество участников (или отправьте '-' чтобы без ограничений):")
    await state.set_state(CreateEventStates.waiting_max_participants)


@router.message(CreateEventStates.waiting_max_participants)
async def process_max_participants(message: Message, state: FSMContext, user: User):
    """Обработка лимита участников"""
    max_participants = None
    
    if message.text and message.text.strip() != "-":
        try:
            max_participants = int(message.text.strip())
            if max_participants <= 0:
                await message.answer("❌ Количество участников должно быть положительным числом.")
                return
        except ValueError:
            await message.answer("❌ Введите число или '-' для отсутствия ограничений.")
            return
    
    data = await state.get_data()
    db = SessionLocal()
    try:
        event = Event(
            title=data['title'],
            description=data.get('description'),
            date_time=data['date_time'],
            status=EventStatus.APPROVED,
            created_by=user.id,
            approved_by=user.id,
            photo_file_id=data.get('photo_file_id'),
            photo_file_ids=data.get('photo_file_ids'),
            max_participants=max_participants
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        
        response_text = f"✅ Событие '{event.title}' создано!\n\n"
        response_text += f"ID: {event.id}\n"
        from utils.timezone import format_event_datetime
        response_text += f"Дата: {format_event_datetime(event.date_time)}\n"
        if data.get('photo_file_id'):
            response_text += f"📷 Фото добавлено\n"
        if max_participants:
            response_text += f"👥 Лимит участников: {max_participants}\n"
        response_text += f"\nТеперь добавьте поля для регистрации через редактирование события."
        
        await message.answer(response_text)
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_registrations_"))
async def admin_view_registrations(callback: CallbackQuery, user: User):
    """Просмотр регистраций на событие"""
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
        
        registrations = db.query(Registration).filter(Registration.event_id == event_id).all()
        
        if not registrations:
            await callback.message.answer(f"На событие '{event.title}' пока нет регистраций.")
            await callback.answer()
            return
        
        text = f"📋 Регистрации на событие: {event.title}\n\n"
        text += f"Всего регистраций: {len(registrations)}"
        if event.max_participants:
            text += f" / {event.max_participants} (лимит)"
            if len(registrations) >= event.max_participants:
                text += " ⚠️ Лимит достигнут"
        text += "\n\n"
        
        keyboard = []
        for i, reg in enumerate(registrations[:20], 1):
            user_obj = db.query(User).filter(User.telegram_id == reg.user_telegram_id).first()
            user_name = user_obj.full_name if user_obj else f"ID: {reg.user_telegram_id}"

            # Статус подтверждения
            if reg.confirmed is True:
                status_text = "✅ Подтверждено"
            elif reg.confirmed is False:
                status_text = "❌ Отказ"
            else:
                status_text = "⏳ Нет ответа"

            text += f"{i}. {user_name} — {status_text}\n"

            # Ссылка на профиль пользователя
            profile_link = None
            if user_obj:
                if user_obj.username:
                    profile_link = f"https://t.me/{user_obj.username}"
                elif user_obj.telegram_id:
                    # Ссылка по ID (откроется в Telegram)
                    profile_link = f"tg://user?id={user_obj.telegram_id}"

            if profile_link:
                text += f"   {profile_link}\n"

            text += f"   Рег.: {reg.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            if reg.data_json:
                # Показываем максимум два поля в одну строку для компактности
                items = list(reg.data_json.items())[:2]
                fields_str = "; ".join(f"{k}: {v}" for k, v in items)
                text += f"   {fields_str}\n"

            # Кнопки действий с регистрацией
            row_buttons = [
                InlineKeyboardButton(
                    text=f"❌ Отменить: {user_name[:18]}",
                    callback_data=f"admin_cancel_reg_{reg.id}"
                ),
                InlineKeyboardButton(
                    text="✉️ Шаблон",
                    callback_data=f"admin_msg_tpl_{reg.id}"
                ),
            ]

            # Кнопка напоминания только если участие не подтверждено
            if reg.confirmed is not True:
                row_buttons.append(
                    InlineKeyboardButton(
                        text="📩 Напомнить",
                        callback_data=f"admin_msg_send_{reg.id}"
                    )
                )

            keyboard.append(row_buttons)
        
        if len(registrations) > 20:
            text += f"\n... и еще {len(registrations) - 20} регистраций"
        
        keyboard.append([InlineKeyboardButton(
            text="📥 Экспорт",
            callback_data=f"admin_export_menu_{event_id}"
        )])
        keyboard.append([InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="admin_events_menu"
        )])
        
        try:
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except:
            await callback.message.answer(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_cancel_reg_"))
async def admin_cancel_registration_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало отмены регистрации администратором"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    registration_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        registration = db.query(Registration).filter(Registration.id == registration_id).first()
        if not registration:
            await callback.answer("Регистрация не найдена.", show_alert=True)
            return
        
        event = db.query(Event).filter(Event.id == registration.event_id).first()
        user_obj = db.query(User).filter(User.telegram_id == registration.user_telegram_id).first()
        user_name = user_obj.full_name if user_obj else f"ID: {registration.user_telegram_id}"
        
        await state.update_data(registration_id=registration_id, user_telegram_id=registration.user_telegram_id, event_id=registration.event_id)
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = [
            [InlineKeyboardButton(
                text="✅ Да, уведомить пользователя",
                callback_data="admin_cancel_notify_yes"
            )],
            [InlineKeyboardButton(
                text="❌ Нет, не уведомлять",
                callback_data="admin_cancel_notify_no"
            )],
            [InlineKeyboardButton(
                text="◀️ Отмена",
                callback_data=f"admin_registrations_{registration.event_id}"
            )]
        ]
        
        await callback.message.answer(
            f"❌ Отмена регистрации\n\n"
            f"Пользователь: {user_name}\n"
            f"Событие: {event.title}\n\n"
            f"Отправить уведомление пользователю об отказе?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.in_(["admin_cancel_notify_yes", "admin_cancel_notify_no"]))
async def admin_cancel_registration_confirm(callback: CallbackQuery, user: User, state: FSMContext):
    """Подтверждение отмены регистрации"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    should_notify = callback.data == "admin_cancel_notify_yes"
    data = await state.get_data()
    registration_id = data.get('registration_id')
    user_telegram_id = data.get('user_telegram_id')
    event_id = data.get('event_id')
    
    if not registration_id:
        await callback.answer("Ошибка: данные не найдены.", show_alert=True)
        await state.clear()
        return
    
    db = SessionLocal()
    try:
        registration = db.query(Registration).filter(Registration.id == registration_id).first()
        if not registration:
            await callback.answer("Регистрация не найдена.", show_alert=True)
            await state.clear()
            return
        
        event = db.query(Event).filter(Event.id == event_id).first()
        user_obj = db.query(User).filter(User.telegram_id == user_telegram_id).first()
        
        # Удаляем запланированные уведомления
        from database.models import ScheduledNotification
        scheduled_notifications = db.query(ScheduledNotification).filter(
            ScheduledNotification.registration_id == registration_id
        ).all()
        for notif in scheduled_notifications:
            db.delete(notif)
        
        # Удаляем регистрацию
        db.delete(registration)
        db.commit()
        
        # Отправляем уведомление пользователю, если нужно
        if should_notify and user_obj:
            try:
                from aiogram import Bot
                from config import settings
                from utils.timezone import format_event_datetime
                bot = Bot(token=settings.BOT_TOKEN)
                await bot.send_message(
                    chat_id=user_telegram_id,
                    text=(
                        f"❌ Ваша регистрация на событие '{event.title}' была отменена администратором.\n\n"
                        f"📆 Дата события: {format_event_datetime(event.date_time)}\n\n"
                        f"Если у вас есть вопросы, обратитесь к организаторам."
                    )
                )
                await bot.session.close()
            except Exception as e:
                # Если не удалось отправить уведомление, просто логируем
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Не удалось отправить уведомление пользователю {user_telegram_id}: {e}")
        
        await callback.answer("✅ Регистрация отменена!", show_alert=True)
        await state.clear()
        
        # Обновляем список регистраций - создаем новый callback с правильным data
        class FakeCallback:
            def __init__(self, original_callback, new_data):
                self.id = original_callback.id
                self.from_user = original_callback.from_user
                self.chat_instance = original_callback.chat_instance
                self.message = original_callback.message
                self.data = new_data
            
            async def answer(self, *args, **kwargs):
                pass
        
        fake_callback = FakeCallback(callback, f"admin_registrations_{event_id}")
        await admin_view_registrations(fake_callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_msg_tpl_"))
async def admin_send_message_template_to_admin(callback: CallbackQuery, user: User):
    """Отправить админу готовый текст-напоминание для копирования"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    registration_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        registration = db.query(Registration).filter(Registration.id == registration_id).first()
        if not registration:
            await callback.answer("Регистрация не найдена.", show_alert=True)
            return
        
        event = db.query(Event).filter(Event.id == registration.event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        from utils.timezone import format_event_datetime
        event_time_str = format_event_datetime(event.date_time) if event.date_time else "без даты/времени"
        
        text = (
            f"Добрый день. Напоминаем вам, что вы записаны на событие '{event.title}' "
            f"в {event_time_str}. Хотели бы подтвердить ваше участие.\n\n"
            "Для уточнения информации о событии и отмены участия вы можете написать в бот "
            "https://t.me/mclassregbot или ответив в этот чат."
        )
        
        await callback.message.answer(text)
        await callback.answer("Шаблон сообщения отправлен. Скопируйте и вставьте в диалог с пользователем.")
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_msg_send_"))
async def admin_send_message_to_user(callback: CallbackQuery, user: User):
    """Отправить пользователю напоминание от имени бота"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    registration_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        registration = db.query(Registration).filter(Registration.id == registration_id).first()
        if not registration:
            await callback.answer("Регистрация не найдена.", show_alert=True)
            return
        
        event = db.query(Event).filter(Event.id == registration.event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        from utils.timezone import format_event_datetime
        event_time_str = format_event_datetime(event.date_time) if event.date_time else "без даты/времени"
        
        text = (
            f"Добрый день. Напоминаем вам, что вы записаны на событие '{event.title}' "
            f"в {event_time_str}. Хотели бы подтвердить ваше участие.\n\n"
            "Для уточнения информации о событии и отмены участия вы можете написать в бот "
            "https://t.me/mclassregbot или ответив в этот чат."
        )
        
        try:
            from aiogram import Bot
            from config import settings
            from bot.handlers.notification_handlers import get_notification_keyboard
            
            bot = Bot(token=settings.BOT_TOKEN)
            await bot.send_message(
                chat_id=registration.user_telegram_id,
                text=text,
                reply_markup=get_notification_keyboard(registration.id)
            )
            await bot.session.close()
            await callback.answer("Напоминание отправлено пользователю.", show_alert=True)
        except Exception as e:
            # Если не удалось отправить сообщение пользователю, уведомляем админа
            await callback.message.answer(f"Не удалось отправить сообщение пользователю: {e}")
            await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_export_menu_"))
async def admin_export_menu(callback: CallbackQuery, user: User):
    """Меню экспорта регистраций"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    await callback.message.answer(
        "Выберите формат экспорта:",
        reply_markup=get_export_format_keyboard(event_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_edit_max_participants_"))
async def admin_edit_max_participants_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало редактирования лимита участников"""
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
        
        current_limit = event.max_participants or "без ограничений"
        await state.update_data(event_id=event_id)
        await callback.message.answer(
            f"Текущий лимит участников: {current_limit}\n\n"
            f"Введите новое значение (число) или отправьте '-' чтобы убрать ограничение:"
        )
        await state.set_state(EditEventStates.waiting_max_participants)
        await callback.answer()
    finally:
        db.close()


@router.message(EditEventStates.waiting_max_participants)
async def process_edit_max_participants(message: Message, state: FSMContext, user: User):
    """Обработка нового лимита участников"""
    if not is_admin(user):
        await message.answer("У вас нет доступа.")
        await state.clear()
        return
    
    max_participants = None
    
    if message.text and message.text.strip() != "-":
        try:
            max_participants = int(message.text.strip())
            if max_participants <= 0:
                await message.answer("❌ Количество участников должно быть положительным числом.")
                return
        except ValueError:
            await message.answer("❌ Введите число или '-' для отсутствия ограничений.")
            return
    
    data = await state.get_data()
    event_id = data['event_id']
    
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await message.answer("Событие не найдено.")
            await state.clear()
            return
        
        # Проверяем, не превышает ли текущее количество регистраций новый лимит
        current_registrations = db.query(Registration).filter(Registration.event_id == event_id).count()
        if max_participants and current_registrations > max_participants:
            await message.answer(
                f"❌ Ошибка! Текущее количество регистраций ({current_registrations}) "
                f"превышает новый лимит ({max_participants}).\n"
                f"Сначала отмените часть регистраций или установите лимит не менее {current_registrations}."
            )
            await state.clear()
            return
        
        event.max_participants = max_participants
        db.commit()
        
        if max_participants:
            await message.answer(f"✅ Лимит участников установлен: {max_participants}")
        else:
            await message.answer("✅ Ограничение на количество участников снято.")
        
        await state.clear()
        
        # Показываем обновленное событие
        from bot.keyboards.admin_keyboards import get_event_actions_keyboard
        
        status_emoji = "⚠️ " if event.status == EventStatus.ARCHIVED else ""
        text = f"{status_emoji}📅 {event.title}\n\n"
        text += f"📝 Описание: {event.description or 'Нет описания'}\n"
        from utils.timezone import format_event_datetime
        text += f"📆 Дата: {format_event_datetime(event.date_time)}\n"
        text += f"📊 Статус: {event.status.value}\n"
        text += f"👤 Создано: {event.creator.full_name or 'Неизвестно'}\n"
        
        registrations_count = len(event.registrations)
        text += f"📋 Регистраций: {registrations_count}"
        if event.max_participants:
            text += f" / {event.max_participants} (лимит)"
            if registrations_count >= event.max_participants:
                text += " ⚠️ Лимит достигнут"
        
        if event.photo_file_id:
            try:
                await message.answer_photo(
                    photo=event.photo_file_id,
                    caption=text,
                    reply_markup=get_event_actions_keyboard(event.id, event.status)
                )
                return
            except Exception:
                pass
        
        await message.answer(text, reply_markup=get_event_actions_keyboard(event.id, event.status))
    finally:
        db.close()


@router.callback_query(F.data == "admin_list_users")
async def admin_list_users(callback: CallbackQuery, user: User):
    """Список пользователей"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        users = db.query(User).order_by(User.created_at.desc()).limit(50).all()
        
        if not users:
            await callback.message.edit_text("Нет пользователей.")
            await callback.answer()
            return
        
        text = "👥 Пользователи:\n\n"
        keyboard = []
        for u in users:
            role_emoji = "👑" if u.role == UserRole.ADMIN else "👤" if u.role == UserRole.ASSISTANT else "👥"
            text += f"{role_emoji} {u.full_name or 'Без имени'}\n"
            text += f"   ID: {u.telegram_id}\n"
            text += f"   Роль: {u.role.value}\n\n"

            # Кнопка действий по пользователю (изменение роли, просмотр регистраций)
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{role_emoji} { (u.full_name or 'Без имени')[:20] }",
                    callback_data=f"admin_user_{u.id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users_menu")])

        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "admin_add_assistant")
async def admin_add_assistant(callback: CallbackQuery, user: User):
    """Выбор пользователя для назначения роли помощника"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return

    db = SessionLocal()
    try:
        # Выбираем только обычных пользователей (без админов и помощников)
        users = db.query(User).filter(User.role == UserRole.USER).order_by(User.created_at.desc()).limit(50).all()

        if not users:
            await callback.answer("Нет пользователей с ролью 'user'.", show_alert=True)
            return

        text = "Выберите пользователя, которому назначить роль помощника:\n\n"
        keyboard = []
        for u in users:
            name = u.full_name or "Без имени"
            text += f"👥 {name} (ID: {u.telegram_id})\n"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"👤 {name[:20]}",
                    callback_data=f"admin_set_role_{u.id}_assistant"
                )
            ])

        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_users_menu")])

        try:
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except Exception:
            await callback.message.answer(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_user_"))
async def admin_user_actions(callback: CallbackQuery, user: User):
    """Меню действий по конкретному пользователю"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return

    data = callback.data
    parts = data.split("_")
    try:
        if data.startswith("admin_user_"):
            target_user_id = int(parts[-1])
        elif data.startswith("admin_set_role_"):
            # admin_set_role_{user_id}_{role}
            target_user_id = int(parts[3])
        else:
            await callback.answer("Некорректные данные.", show_alert=True)
            return
    except (IndexError, ValueError):
        await callback.answer("Некорректные данные.", show_alert=True)
        return
    db = SessionLocal()
    try:
        target = db.query(User).filter(User.id == target_user_id).first()
        if not target:
            await callback.answer("Пользователь не найден.", show_alert=True)
            return

        text = (
            f"👤 Пользователь: {target.full_name or 'Без имени'}\n"
            f"ID: {target.telegram_id}\n"
            f"Текущая роль: {target.role.value}\n\n"
            "Выберите действие:"
        )

        keyboard = get_user_actions_keyboard(target_user_id)

        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except Exception:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_change_role_"))
async def admin_change_role(callback: CallbackQuery, user: User):
    """Показать выбор роли для пользователя"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return

    target_user_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        target = db.query(User).filter(User.id == target_user_id).first()
        if not target:
            await callback.answer("Пользователь не найден.", show_alert=True)
            return

        text = (
            f"Изменение роли для пользователя:\n"
            f"{target.full_name or 'Без имени'} (ID: {target.telegram_id})\n"
            f"Текущая роль: {target.role.value}\n\n"
            "Выберите новую роль:"
        )

        keyboard = get_role_selection_keyboard(target_user_id)

        try:
            await callback.message.edit_text(text, reply_markup=keyboard)
        except Exception:
            await callback.message.answer(text, reply_markup=keyboard)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_set_role_"))
async def admin_set_role(callback: CallbackQuery, user: User):
    """Установить роль пользователю"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return

    parts = callback.data.split("_")
    # admin_set_role_{user_id}_{role}
    try:
        target_user_id = int(parts[3])
        role_name = parts[4]
    except (IndexError, ValueError):
        await callback.answer("Некорректные данные.", show_alert=True)
        return

    db = SessionLocal()
    try:
        target = db.query(User).filter(User.id == target_user_id).first()
        if not target:
            await callback.answer("Пользователь не найден.", show_alert=True)
            return

        if role_name == "admin":
            target.role = UserRole.ADMIN
        elif role_name == "assistant":
            target.role = UserRole.ASSISTANT
        elif role_name == "user":
            target.role = UserRole.USER
        else:
            await callback.answer("Неизвестная роль.", show_alert=True)
            return

        db.commit()

        await callback.answer("Роль обновлена.", show_alert=True)

        # Возвращаемся к действиям по пользователю
        await admin_user_actions(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_approve_"))
async def admin_approve_event(callback: CallbackQuery, user: User):
    """Утверждение события"""
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
        
        event.status = EventStatus.APPROVED
        event.approved_by = user.id
        db.commit()
        
        await callback.answer("✅ Событие утверждено!", show_alert=True)
        await admin_event_detail(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_archive_"))
async def admin_archive_event(callback: CallbackQuery, user: User):
    """Архивирование события"""
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
        
        event.status = EventStatus.ARCHIVED
        db.commit()
        
        await callback.answer("⚠️ Событие архивировано!", show_alert=True)
        await admin_event_detail(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_unarchive_"))
async def admin_unarchive_event(callback: CallbackQuery, user: User):
    """Разархивирование события"""
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
        
        event.status = EventStatus.ACTIVE
        db.commit()
        
        await callback.answer("✅ Событие разархивировано!", show_alert=True)
        await admin_event_detail(callback, user)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_delete_event_"))
async def admin_delete_event_confirm(callback: CallbackQuery, user: User):
    """Подтверждение удаления события"""
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
        
        registrations_count = db.query(Registration).filter(Registration.event_id == event_id).count()
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        text = f"🗑️ УДАЛЕНИЕ СОБЫТИЯ\n\n"
        text += f"📅 {event.title}\n"
        from utils.timezone import format_event_datetime
        text += f"📆 Дата: {format_event_datetime(event.date_time)}\n"
        text += f"📋 Регистраций: {registrations_count}\n\n"
        text += f"⚠️ ВНИМАНИЕ! Это действие необратимо!\n"
        text += f"Будут удалены:\n"
        text += f"• Событие\n"
        text += f"• Все регистрации ({registrations_count})\n"
        text += f"• Все запланированные уведомления\n"
        text += f"• Все настройки уведомлений\n"
        text += f"• Все права доступа\n\n"
        text += f"Вы уверены, что хотите удалить это событие?"
        
        keyboard = [
            [InlineKeyboardButton(
                text="✅ Да, удалить",
                callback_data=f"admin_delete_confirm_{event_id}"
            )],
            [InlineKeyboardButton(
                text="❌ Отмена",
                callback_data=f"admin_event_{event_id}"
            )]
        ]
        
        try:
            await callback.message.edit_text(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        except:
            await callback.message.answer(
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
            )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_delete_confirm_"))
async def admin_delete_event(callback: CallbackQuery, user: User):
    """Удаление события"""
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
        
        event_title = event.title
        registrations_count = db.query(Registration).filter(Registration.event_id == event_id).count()
        
        # Удаляем событие (каскадное удаление удалит все связанные записи)
        db.delete(event)
        db.commit()
        
        await callback.answer(f"✅ Событие '{event_title}' удалено!", show_alert=True)
        
        # Возвращаемся к списку событий
        from bot.keyboards.common_keyboards import get_events_list_keyboard
        
        events = db.query(Event).order_by(Event.date_time.desc()).limit(20).all()
        if events:
            await callback.message.answer(
                "Выберите событие:",
                reply_markup=get_events_list_keyboard(events, "admin_event")
            )
        else:
            await callback.message.answer("Нет событий.")
        
        try:
            await callback.message.delete()
        except:
            pass
    finally:
        db.close()


@router.callback_query(F.data == "admin_drafts")
async def admin_drafts(callback: CallbackQuery, user: User):
    """Список черновиков"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        drafts = db.query(Event).filter(Event.status == EventStatus.DRAFT).order_by(Event.created_at.desc()).all()
        
        if not drafts:
            await callback.message.edit_text("Нет черновиков.")
            return
        
        from bot.keyboards.common_keyboards import get_events_list_keyboard
        await callback.message.edit_text(
            "Черновики событий:",
            reply_markup=get_events_list_keyboard(drafts, "admin_event")
        )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "admin_pending_approval")
async def admin_pending_approval(callback: CallbackQuery, user: User):
    """События на утверждение"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        pending = db.query(Event).filter(Event.status == EventStatus.DRAFT).order_by(Event.created_at.desc()).all()
        
        if not pending:
            await callback.message.edit_text("Нет событий на утверждение.")
            return
        
        from bot.keyboards.common_keyboards import get_events_list_keyboard
        await callback.message.edit_text(
            "События на утверждение:",
            reply_markup=get_events_list_keyboard(pending, "admin_event")
        )
        await callback.answer()
    finally:
        db.close()

