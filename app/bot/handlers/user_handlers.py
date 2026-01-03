from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import User, Event, EventStatus, Registration, EventField, FieldType
from database.database import SessionLocal
from datetime import datetime
from utils.timezone import get_local_now
from bot.keyboards.common_keyboards import get_events_list_keyboard
import json

router = Router()


class RegistrationStates(StatesGroup):
    waiting_field_value = State()


@router.message(F.text == "📅 События")
async def user_show_events(message: Message, user: User):
    """Показать список событий для обычного пользователя"""
    db = SessionLocal()
    try:
        events = db.query(Event).filter(
            Event.status.in_([EventStatus.APPROVED, EventStatus.ACTIVE])
        ).order_by(Event.date_time.asc()).all()
        
        if not events:
            await message.answer("📅 Нет доступных событий.")
            return
        
        await message.answer(
            "📅 Доступные события:",
            reply_markup=get_events_list_keyboard(events, "user_event")
        )
    finally:
        db.close()


@router.callback_query(F.data.startswith("user_event_"))
async def user_event_detail(callback: CallbackQuery, user: User, bot: Bot):
    """Детали события для пользователя"""
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        if event.status not in [EventStatus.APPROVED, EventStatus.ACTIVE]:
            await callback.answer("Событие недоступно.", show_alert=True)
            return
        
        # Проверяем, зарегистрирован ли уже пользователь
        existing_reg = db.query(Registration).filter(
            Registration.event_id == event_id,
            Registration.user_telegram_id == user.telegram_id
        ).first()
        
        # Проверяем, не прошло ли событие (сравниваем с локальным временем)
        from utils.timezone import utc_to_local, get_local_now
        if event.date_time:
            event_local_time = utc_to_local(event.date_time)
            is_past_event = event_local_time < get_local_now()
        else:
            is_past_event = False
        
        from utils.timezone import format_event_datetime
        
        text = f"📅 {event.title}\n\n"
        text += f"📝 Описание: {event.description or 'Нет описания'}\n"
        text += f"📆 Дата: {format_event_datetime(event.date_time)}\n"
        
        # Показываем информацию о лимите
        if event.max_participants:
            current_count = db.query(Registration).filter(Registration.event_id == event_id).count()
            text += f"👥 Мест: {current_count}/{event.max_participants}\n"
            if current_count >= event.max_participants:
                text += "⚠️ Все места заняты\n"
        
        if existing_reg:
            text += "\n✅ Вы уже зарегистрированы на это событие!"
            if not is_past_event:
                text += "\nВы можете отменить регистрацию, если передумали."
        elif is_past_event:
            text += "\n⚠️ Это событие уже прошло. Регистрация недоступна."
        else:
            text += "\n📋 Для регистрации заполните форму ниже."
        
        # Отправляем фото, если есть и у нас есть исходное message (в inline‑сообщениях его может не быть)
        if event.photo_file_id and callback.message:
            try:
                # Проверяем доступность файла
                try:
                    file = await bot.get_file(event.photo_file_id)
                    # Если файл доступен, отправляем фото с коротким caption (Telegram ограничивает до 1024 символов)
                    # Создаем короткий caption только с названием и датой
                    short_caption = f"📅 {event.title}\n📆 {format_event_datetime(event.date_time)}"
                    if len(short_caption) > 1024:
                        short_caption = short_caption[:1021] + "..."
                    
                    keyboard = []
                    if not existing_reg and not is_past_event:
                        keyboard.append([InlineKeyboardButton(
                            text="📝 Зарегистрироваться",
                            callback_data=f"user_register_{event_id}"
                        )])
                    elif existing_reg and not is_past_event:
                        keyboard.append([InlineKeyboardButton(
                            text="❌ Отменить регистрацию",
                            callback_data=f"user_cancel_registration_{event_id}"
                        )])
                    keyboard.append([InlineKeyboardButton(
                        text="◀️ Назад к списку",
                        callback_data="user_events_list"
                    )])
                    
                    # Отправляем фото с коротким caption
                    await callback.message.answer_photo(
                        photo=event.photo_file_id,
                        caption=short_caption,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
                    )
                    
                    # Отправляем полный текст отдельным сообщением
                    await callback.message.answer(
                        text,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
                    )
                    
                    try:
                        await callback.message.delete()
                    except:
                        pass
                    await callback.answer()
                    return
                except Exception as file_error:
                    # Если файл недоступен, логируем и продолжаем без фото
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Файл фото недоступен для события {event_id}: {str(file_error)}. Отправляем текстовое сообщение.")
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Ошибка при отправке фото события {event_id}: {str(e)}", exc_info=True)
                # Продолжаем отправку текстового сообщения
        
        # Формируем клавиатуру для текстового сообщения
        keyboard = []
        if not existing_reg and not is_past_event:
            keyboard.append([InlineKeyboardButton(
                text="📝 Зарегистрироваться",
                callback_data=f"user_register_{event_id}"
            )])
        elif existing_reg and not is_past_event:
            keyboard.append([InlineKeyboardButton(
                text="❌ Отменить регистрацию",
                callback_data=f"user_cancel_registration_{event_id}"
            )])
        elif is_past_event:
            text += "\n⚠️ Это событие уже прошло. Регистрация недоступна."
        keyboard.append([InlineKeyboardButton(
            text="◀️ Назад к списку",
            callback_data="user_events_list"
        )])
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None

        if callback.message:
            # Обычное сообщение в чате
            await callback.message.edit_text(
                text,
                reply_markup=reply_markup
            )
        elif callback.inline_message_id:
            # Сообщение, отправленное через inline‑режим (message=None)
            await bot.edit_message_text(
                text=text,
                inline_message_id=callback.inline_message_id,
                reply_markup=reply_markup
            )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data == "user_events_list")
async def user_events_list(callback: CallbackQuery, user: User):
    """Вернуться к списку событий"""
    await user_show_events(callback.message, user)
    await callback.answer()


@router.callback_query(F.data.startswith("user_register_"))
async def user_start_registration(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало регистрации на событие"""
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        # Проверяем, не прошло ли событие (сравниваем с локальным временем)
        from utils.timezone import utc_to_local, get_local_now
        if event.date_time:
            event_local_time = utc_to_local(event.date_time)
            if event_local_time < get_local_now():
                await callback.answer("❌ Регистрация на прошедшие события недоступна!", show_alert=True)
                return
        
        # Проверяем, зарегистрирован ли уже
        existing_reg = db.query(Registration).filter(
            Registration.event_id == event_id,
            Registration.user_telegram_id == user.telegram_id
        ).first()
        
        if existing_reg:
            await callback.answer("Вы уже зарегистрированы на это событие!", show_alert=True)
            return
        
        # Проверяем лимит участников
        current_registrations_count = db.query(Registration).filter(Registration.event_id == event_id).count()
        if event.max_participants and current_registrations_count >= event.max_participants:
            await callback.answer(
                f"❌ К сожалению, все места заняты! Лимит: {event.max_participants} участников.",
                show_alert=True
            )
            return
        
        # Получаем поля для регистрации
        fields = sorted(event.fields, key=lambda x: x.order)
        
        if not fields:
            # Если полей нет, регистрируем сразу
            registration = Registration(
                event_id=event_id,
                user_telegram_id=user.telegram_id,
                data_json={}
            )
            db.add(registration)
            db.commit()
            db.refresh(registration)
            
            # Создаем запланированные уведомления для новой регистрации
            from services.notification_service import create_scheduled_notifications_for_event
            create_scheduled_notifications_for_event(db, event)
            
            await callback.answer("✅ Вы успешно зарегистрированы!", show_alert=True)
            await user_event_detail(callback, user)
            return
        
        # Сохраняем данные для регистрации
        await state.update_data(event_id=event_id, fields=fields, current_field_index=0, data={})
        
        # Начинаем заполнение первого поля
        first_field = fields[0]
        text = f"📝 Регистрация на событие: {event.title}\n\n"
        text += f"Заполните поле: {first_field.field_name}"
        if first_field.required:
            text += " (обязательное)"
        text += f"\nТип: {first_field.field_type.value}"
        
        if first_field.field_type == FieldType.SELECT and first_field.options:
            text += "\n\nВарианты:\n"
            for i, option in enumerate(first_field.options, 1):
                text += f"{i}. {option}\n"
        
        await callback.message.answer(text)
        await state.set_state(RegistrationStates.waiting_field_value)
        await callback.answer()
    finally:
        db.close()


@router.message(RegistrationStates.waiting_field_value)
async def process_field_value(message: Message, state: FSMContext, user: User):
    """Обработка значения поля"""
    data = await state.get_data()
    event_id = data['event_id']
    fields = data['fields']
    current_index = data['current_field_index']
    registration_data = data.get('data', {})
    
    current_field = fields[current_index]
    field_value = message.text.strip()
    
    # Валидация
    if current_field.required and not field_value:
        await message.answer(f"❌ Поле '{current_field.field_name}' обязательно для заполнения.")
        return
    
    # Валидация по типу
    if current_field.field_type == FieldType.EMAIL:
        if "@" not in field_value:
            await message.answer("❌ Введите корректный email адрес.")
            return
    elif current_field.field_type == FieldType.PHONE:
        if not field_value.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "").isdigit():
            await message.answer("❌ Введите корректный номер телефона.")
            return
    elif current_field.field_type == FieldType.NUMBER:
        try:
            float(field_value)
        except ValueError:
            await message.answer("❌ Введите число.")
            return
    elif current_field.field_type == FieldType.DATE:
        try:
            datetime.strptime(field_value, "%d.%m.%Y")
        except ValueError:
            await message.answer("❌ Введите дату в формате ДД.ММ.ГГГГ")
            return
    elif current_field.field_type == FieldType.SELECT:
        if current_field.options:
            # Проверяем, что выбран один из вариантов
            if field_value not in current_field.options:
                # Пробуем по номеру
                try:
                    option_index = int(field_value) - 1
                    if 0 <= option_index < len(current_field.options):
                        field_value = current_field.options[option_index]
                    else:
                        await message.answer(f"❌ Выберите один из вариантов (1-{len(current_field.options)}).")
                        return
                except ValueError:
                    await message.answer(f"❌ Выберите один из вариантов (1-{len(current_field.options)}).")
                    return
    
    # Сохраняем значение
    registration_data[current_field.field_name] = field_value
    
    # Переходим к следующему полю
    next_index = current_index + 1
    
    if next_index < len(fields):
        # Есть еще поля
        await state.update_data(current_field_index=next_index, data=registration_data)
        
        next_field = fields[next_index]
        text = f"✅ {current_field.field_name}: {field_value}\n\n"
        text += f"Следующее поле: {next_field.field_name}"
        if next_field.required:
            text += " (обязательное)"
        text += f"\nТип: {next_field.field_type.value}"
        
        if next_field.field_type == FieldType.SELECT and next_field.options:
            text += "\n\nВарианты:\n"
            for i, option in enumerate(next_field.options, 1):
                text += f"{i}. {option}\n"
        
        await message.answer(text)
    else:
        # Все поля заполнены, сохраняем регистрацию
        db = SessionLocal()
        try:
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                await message.answer("❌ Событие не найдено.")
                await state.clear()
                return
            
            registration = Registration(
                event_id=event_id,
                user_telegram_id=user.telegram_id,
                data_json=registration_data
            )
            db.add(registration)
            db.commit()
            db.refresh(registration)
            
            # Создаем запланированные уведомления для новой регистрации
            from services.notification_service import create_scheduled_notifications_for_event
            create_scheduled_notifications_for_event(db, event)
            
            from utils.timezone import format_event_datetime
            await message.answer(
                f"✅ Вы успешно зарегистрированы на событие '{event.title}'!\n\n"
                f"📆 Дата события: {format_event_datetime(event.date_time)}\n\n"
                f"Ваши данные:\n" + "\n".join([f"• {k}: {v}" for k, v in registration_data.items()])
            )
            await state.clear()
        finally:
            db.close()


@router.callback_query(F.data.startswith("user_cancel_registration_"))
async def user_cancel_registration(callback: CallbackQuery, user: User):
    """Отмена регистрации на событие"""
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        # Проверяем, не прошло ли событие (сравниваем с локальным временем)
        from utils.timezone import utc_to_local, get_local_now
        if event.date_time:
            event_local_time = utc_to_local(event.date_time)
            if event_local_time < get_local_now():
                await callback.answer("❌ Нельзя отменить регистрацию на прошедшее событие!", show_alert=True)
                return
        
        # Находим регистрацию
        registration = db.query(Registration).filter(
            Registration.event_id == event_id,
            Registration.user_telegram_id == user.telegram_id
        ).first()
        
        if not registration:
            await callback.answer("Вы не зарегистрированы на это событие.", show_alert=True)
            return
        
        # Удаляем запланированные уведомления для этой регистрации
        from database.models import ScheduledNotification
        scheduled_notifications = db.query(ScheduledNotification).filter(
            ScheduledNotification.registration_id == registration.id
        ).all()
        for notif in scheduled_notifications:
            db.delete(notif)
        
        # Удаляем регистрацию
        db.delete(registration)
        db.commit()
        
        await callback.answer("✅ Регистрация отменена!", show_alert=True)
        
        # Обновляем информацию о событии
        await user_event_detail(callback, user)
    finally:
        db.close()


@router.message(F.text == "📋 Мои регистрации")
async def user_my_registrations(message: Message, user: User):
    """Показать регистрации пользователя"""
    db = SessionLocal()
    try:
        registrations = db.query(Registration).filter(
            Registration.user_telegram_id == user.telegram_id
        ).order_by(Registration.created_at.desc()).all()
        
        if not registrations:
            await message.answer("📋 У вас пока нет регистраций на события.")
            return
        
        text = "📋 Ваши регистрации:\n\n"
        
        for i, reg in enumerate(registrations[:10], 1):
            event = db.query(Event).filter(Event.id == reg.event_id).first()
            if event:
                from utils.timezone import format_event_datetime
                text += f"{i}. 📅 {event.title}\n"
                text += f"   Дата: {format_event_datetime(event.date_time)}\n"
                text += f"   Зарегистрирован: {reg.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                if reg.data_json:
                    for key, value in list(reg.data_json.items())[:2]:
                        text += f"   {key}: {value}\n"
                text += "\n"
        
        if len(registrations) > 10:
            text += f"\n... и еще {len(registrations) - 10} регистраций"
        
        await message.answer(text)
    finally:
        db.close()

