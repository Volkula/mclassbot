from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import User, NotificationTemplate, EventNotification, Event
from bot.keyboards.admin_keyboards import get_admin_events_menu
from utils.permissions import is_admin
from database.database import SessionLocal
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


class CreateTemplateStates(StatesGroup):
    waiting_name = State()
    waiting_time_type = State()
    waiting_time_minutes = State()
    waiting_time_days = State()
    waiting_time_datetime = State()
    waiting_message = State()


@router.message(F.text == "⚙️ Настройки")
async def admin_settings_menu(message: Message, user: User):
    """Меню настроек для админа"""
    if not is_admin(user):
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    text = "⚙️ НАСТРОЙКИ\n\n"
    text += "Выберите раздел:"
    
    keyboard = [
        [InlineKeyboardButton(text="🔔 Шаблоны уведомлений", callback_data="settings_templates")],
        [InlineKeyboardButton(text="📊 Статистика системы", callback_data="settings_stats")],
        [InlineKeyboardButton(text="👥 Управление ролями", callback_data="settings_roles")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="back_to_main")],
    ]
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@router.callback_query(F.data == "settings_templates")
async def settings_templates_menu(callback: CallbackQuery, user: User):
    """Меню шаблонов уведомлений"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        templates = db.query(NotificationTemplate).order_by(NotificationTemplate.created_at.desc()).all()
        
        text = "🔔 ШАБЛОНЫ УВЕДОМЛЕНИЙ\n\n"
        
        if templates:
            for template in templates:
                text += f"📋 {template.name}\n"
                if template.absolute_datetime:
                    text += f"   Время: {template.absolute_datetime.strftime('%d.%m.%Y %H:%M')}\n"
                elif template.time_before_event:
                    days = template.time_before_event // (24 * 60)
                    hours = (template.time_before_event % (24 * 60)) // 60
                    minutes = template.time_before_event % 60
                    if days > 0:
                        text += f"   Время: за {days} дн. {hours} ч. {minutes} мин. до события\n"
                    elif hours > 0:
                        text += f"   Время: за {hours} ч. {minutes} мин. до события\n"
                    else:
                        text += f"   Время: за {minutes} мин. до события\n"
                text += f"   Шаблон: {template.message_template[:50]}...\n\n"
        else:
            text += "Шаблоны не созданы.\n\n"
        
        keyboard = [
            [InlineKeyboardButton(text="➕ Создать шаблон", callback_data="template_create")],
            [InlineKeyboardButton(text="📋 Список шаблонов", callback_data="template_list")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")],
        ]
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "template_create")
async def template_create_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало создания шаблона"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    await callback.message.answer("Создание шаблона уведомления.\nВведите название шаблона:")
    await state.set_state(CreateTemplateStates.waiting_name)
    await callback.answer()


@router.message(CreateTemplateStates.waiting_name)
async def process_template_name(message: Message, state: FSMContext):
    """Обработка названия шаблона"""
    await state.update_data(name=message.text)
    text = "Выберите формат времени уведомления:\n\n"
    text += "1️⃣ Минуты до события (например, 60 для уведомления за час)\n"
    text += "2️⃣ Дни до события (например, 1 для уведомления за день)\n"
    text += "3️⃣ Конкретная дата и время (например, 15.12.2025 10:00)\n\n"
    text += "Отправьте номер (1, 2 или 3):"
    await message.answer(text)
    await state.set_state(CreateTemplateStates.waiting_time_type)


@router.message(CreateTemplateStates.waiting_time_type)
async def process_template_time_type(message: Message, state: FSMContext):
    """Обработка типа времени уведомления"""
    choice = message.text.strip()
    
    if choice == "1":
        await state.update_data(time_type="minutes")
        await message.answer("Введите время уведомления в минутах до события (например, 60 для уведомления за час):")
        await state.set_state(CreateTemplateStates.waiting_time_minutes)
    elif choice == "2":
        await state.update_data(time_type="days")
        await message.answer("Введите количество дней до события (например, 1 для уведомления за день, 7 за неделю):")
        await state.set_state(CreateTemplateStates.waiting_time_days)
    elif choice == "3":
        await state.update_data(time_type="datetime")
        await message.answer("Введите конкретную дату и время уведомления в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
                           "Например: 15.12.2025 10:00")
        await state.set_state(CreateTemplateStates.waiting_time_datetime)
    else:
        await message.answer("❌ Неверный выбор. Отправьте 1, 2 или 3.")


@router.message(CreateTemplateStates.waiting_time_minutes)
async def process_template_time_minutes(message: Message, state: FSMContext):
    """Обработка времени в минутах"""
    try:
        time_minutes = int(message.text.strip())
        await state.update_data(time_before_event=time_minutes)
        await message.answer("Введите текст шаблона сообщения.\n\n"
                           "Доступные переменные:\n"
                           "{event_title} - название события\n"
                           "{event_date} - дата события\n"
                           "{event_description} - описание события")
        await state.set_state(CreateTemplateStates.waiting_message)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (минуты до события).")


@router.message(CreateTemplateStates.waiting_time_days)
async def process_template_time_days(message: Message, state: FSMContext):
    """Обработка времени в днях"""
    try:
        time_days = int(message.text.strip())
        # Конвертируем дни в минуты
        time_minutes = time_days * 24 * 60
        await state.update_data(time_before_event=time_minutes)
        await message.answer("Введите текст шаблона сообщения.\n\n"
                           "Доступные переменные:\n"
                           "{event_title} - название события\n"
                           "{event_date} - дата события\n"
                           "{event_description} - описание события")
        await state.set_state(CreateTemplateStates.waiting_message)
    except ValueError:
        await message.answer("❌ Неверный формат. Введите число (дни до события).")


@router.message(CreateTemplateStates.waiting_time_datetime)
async def process_template_time_datetime(message: Message, state: FSMContext):
    """Обработка конкретной даты и времени"""
    try:
        from utils.timezone import parse_local_datetime, local_to_utc
        
        datetime_str = message.text.strip()
        notification_datetime_local = parse_local_datetime(datetime_str, "%d.%m.%Y %H:%M")
        # Конвертируем в UTC для хранения в БД
        notification_datetime_utc = local_to_utc(notification_datetime_local)
        
        # Сохраняем как абсолютное время (будет использоваться специальная логика)
        await state.update_data(
            time_before_event=None,
            absolute_datetime=notification_datetime_utc.isoformat()
        )
        await message.answer("Введите текст шаблона сообщения.\n\n"
                           "Доступные переменные:\n"
                           "{event_title} - название события\n"
                           "{event_date} - дата события\n"
                           "{event_description} - описание события")
        await state.set_state(CreateTemplateStates.waiting_message)
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
                           "Например: 15.12.2025 10:00")


@router.message(CreateTemplateStates.waiting_message)
async def process_template_message(message: Message, state: FSMContext, user: User):
    """Обработка текста шаблона"""
    data = await state.get_data()
    db = SessionLocal()
    try:
        absolute_datetime = None
        if 'absolute_datetime' in data and data['absolute_datetime']:
            absolute_datetime = datetime.fromisoformat(data['absolute_datetime'])
        
        template = NotificationTemplate(
            name=data['name'],
            time_before_event=data.get('time_before_event'),
            absolute_datetime=absolute_datetime,
            message_template=message.text
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        
        time_info = ""
        if template.absolute_datetime:
            time_info = f"Дата и время: {template.absolute_datetime.strftime('%d.%m.%Y %H:%M')}"
        elif template.time_before_event:
            days = template.time_before_event // (24 * 60)
            hours = (template.time_before_event % (24 * 60)) // 60
            minutes = template.time_before_event % 60
            
            if days > 0:
                time_info = f"За {days} дн. {hours} ч. {minutes} мин. до события"
            elif hours > 0:
                time_info = f"За {hours} ч. {minutes} мин. до события"
            else:
                time_info = f"За {minutes} мин. до события"
        
        await message.answer(f"✅ Шаблон '{template.name}' создан!\n\n"
                           f"ID: {template.id}\n"
                           f"{time_info}")
        await state.clear()
    finally:
        db.close()


@router.callback_query(F.data == "template_list")
async def template_list(callback: CallbackQuery, user: User):
    """Список шаблонов"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        templates = db.query(NotificationTemplate).order_by(NotificationTemplate.created_at.desc()).all()
        
        if not templates:
            await callback.message.edit_text("Нет шаблонов.")
            await callback.answer()
            return
        
        text = "📋 ШАБЛОНЫ УВЕДОМЛЕНИЙ\n\n"
        keyboard = []
        
        for template in templates:
            text += f"📋 {template.name}\n"
            text += f"   ID: {template.id}\n"
            text += f"   Время: за {template.time_before_event} минут\n"
            text += f"   Текст: {template.message_template[:100]}...\n\n"
            
            keyboard.append([InlineKeyboardButton(
                text=f"📋 {template.name}",
                callback_data=f"template_view_{template.id}"
            )])
        
        keyboard.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings_templates")])
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("template_view_"))
async def template_view(callback: CallbackQuery, user: User):
    """Просмотр шаблона"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    template_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
        if not template:
            await callback.answer("Шаблон не найден.", show_alert=True)
            return
        
        text = f"📋 {template.name}\n\n"
        text += f"ID: {template.id}\n"
        if template.absolute_datetime:
            text += f"Время уведомления: {template.absolute_datetime.strftime('%d.%m.%Y %H:%M')}\n"
        elif template.time_before_event:
            days = template.time_before_event // (24 * 60)
            hours = (template.time_before_event % (24 * 60)) // 60
            minutes = template.time_before_event % 60
            if days > 0:
                text += f"Время уведомления: за {days} дн. {hours} ч. {minutes} мин. до события\n"
            elif hours > 0:
                text += f"Время уведомления: за {hours} ч. {minutes} мин. до события\n"
            else:
                text += f"Время уведомления: за {minutes} мин. до события\n"
        text += f"Создан: {template.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        text += f"Текст шаблона:\n{template.message_template}\n\n"
        text += "Доступные переменные:\n"
        text += "{event_title} - название события\n"
        text += "{event_date} - дата события\n"
        text += "{event_description} - описание события"
        
        keyboard = [
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"template_delete_{template_id}")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="template_list")],
        ]
        
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("template_delete_"))
async def template_delete(callback: CallbackQuery, user: User):
    """Удаление шаблона"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    template_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        template = db.query(NotificationTemplate).filter(NotificationTemplate.id == template_id).first()
        if not template:
            await callback.answer("Шаблон не найден.", show_alert=True)
            return
        
        db.delete(template)
        db.commit()
        
        await callback.answer("✅ Шаблон удален!", show_alert=True)
        await template_list(callback, user)
    finally:
        db.close()


@router.callback_query(F.data == "settings_stats")
async def settings_stats(callback: CallbackQuery, user: User):
    """Статистика системы"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        from database.models import Event, Registration, User as UserModel
        
        total_events = db.query(Event).count()
        active_events = db.query(Event).filter(Event.status.in_(["approved", "active"])).count()
        total_registrations = db.query(Registration).count()
        total_users = db.query(UserModel).count()
        from database.models import UserRole
        admin_users = db.query(UserModel).filter(UserModel.role == UserRole.ADMIN).count()
        assistant_users = db.query(UserModel).filter(UserModel.role == UserRole.ASSISTANT).count()
        
        text = "📊 СТАТИСТИКА СИСТЕМЫ\n\n"
        text += f"📅 События:\n"
        text += f"   Всего: {total_events}\n"
        text += f"   Активных: {active_events}\n\n"
        text += f"👥 Пользователи:\n"
        text += f"   Всего: {total_users}\n"
        text += f"   Админов: {admin_users}\n"
        text += f"   Помощников: {assistant_users}\n\n"
        text += f"📋 Регистрации:\n"
        text += f"   Всего: {total_registrations}\n"
        
        keyboard = [[InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")]]
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "settings_roles")
async def settings_roles(callback: CallbackQuery, user: User):
    """Управление ролями"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👥 Управление ролями пользователей доступно через меню '👥 Пользователи'.\n\n"
        "Там вы можете:\n"
        "• Просмотреть список пользователей\n"
        "• Изменить роль пользователя\n"
        "• Назначить помощника",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")
        ]])
    )
    await callback.answer()


@router.callback_query(F.data == "settings_back")
async def settings_back(callback: CallbackQuery, user: User):
    """Возврат в меню настроек"""
    if not is_admin(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    await admin_settings_menu(callback.message, user)
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, user: User):
    """Возврат в главное меню"""
    from bot.keyboards.common_keyboards import get_main_menu_keyboard
    await callback.message.answer(
        "Главное меню",
        reply_markup=get_main_menu_keyboard(user.role, view_as_user=False)
    )
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer()

