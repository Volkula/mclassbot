from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import User, Event, EventStatus, EventField, FieldType
from bot.keyboards.admin_keyboards import get_event_actions_keyboard
from bot.keyboards.assistant_keyboards import get_assistant_event_actions_keyboard
from utils.permissions import is_admin, can_edit_event, can_view_registrations
from database.database import SessionLocal
from datetime import datetime

router = Router()


class EditEventStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_date = State()
    waiting_photo = State()
    waiting_max_participants = State()


class AddFieldStates(StatesGroup):
    waiting_field_name = State()
    waiting_field_type = State()
    waiting_required = State()
    waiting_options = State()


@router.callback_query(F.data.startswith("admin_edit_"))
async def admin_edit_event_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало редактирования события админом"""
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
        await callback.message.answer(f"Редактирование события: {event.title}\n\nВведите новое название (или отправьте '-' чтобы оставить текущее):")
        await state.set_state(EditEventStates.waiting_title)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("assistant_edit_"))
async def assistant_edit_event_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало редактирования события помощником"""
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        if not can_edit_event(db, user, event_id):
            await callback.answer("У вас нет прав на редактирование этого события.", show_alert=True)
            return
        
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        await state.update_data(event_id=event_id)
        await callback.message.answer(f"Редактирование события: {event.title}\n\nВведите новое название (или отправьте '-' чтобы оставить текущее):")
        await state.set_state(EditEventStates.waiting_title)
        await callback.answer()
    finally:
        db.close()


@router.message(EditEventStates.waiting_title)
async def process_edit_title(message: Message, state: FSMContext):
    """Обработка нового названия"""
    title = message.text if message.text != "-" else None
    await state.update_data(title=title)
    await message.answer("Введите новое описание (или отправьте '-' чтобы оставить текущее, '--' чтобы удалить):")
    await state.set_state(EditEventStates.waiting_description)


@router.message(EditEventStates.waiting_description)
async def process_edit_description(message: Message, state: FSMContext):
    """Обработка нового описания"""
    description = None
    if message.text == "-":
        description = None  # Оставить текущее
    elif message.text == "--":
        description = ""  # Удалить
    else:
        description = message.text
    
    await state.update_data(description=description)
    await message.answer("Введите новую дату и время в формате ДД.ММ.ГГГГ ЧЧ:ММ (или отправьте '-' чтобы оставить текущую):")
    await state.set_state(EditEventStates.waiting_date)


@router.message(EditEventStates.waiting_date)
async def process_edit_date(message: Message, state: FSMContext, user: User):
    """Обработка новой даты"""
    data = await state.get_data()
    event_id = data['event_id']
    
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await message.answer("Событие не найдено.")
            await state.clear()
            return
        
        # Обновляем поля
        if data.get('title') is not None:
            event.title = data['title']
        
        if 'description' in data:
            if data['description'] is not None:
                event.description = data['description'] if data['description'] != "" else None
        
        if message.text != "-":
            try:
                from utils.timezone import parse_local_datetime
                date_time = parse_local_datetime(message.text.strip(), "%d.%m.%Y %H:%M")
                event.date_time = date_time
            except ValueError:
                await message.answer("❌ Неверный формат даты. Используйте формат: ДД.ММ.ГГГГ ЧЧ:ММ")
                return
        
        db.commit()
        db.refresh(event)
        
        await message.answer("Отправьте новое фото для события (или отправьте '-' чтобы оставить текущее, '--' чтобы удалить):")
        await state.set_state(EditEventStates.waiting_photo)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin_add_field_"))
async def admin_add_field_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало добавления поля к событию"""
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
        await callback.message.answer("Добавление поля для регистрации.\nВведите название поля:")
        await state.set_state(AddFieldStates.waiting_field_name)
        await callback.answer()
    finally:
        db.close()


@router.message(AddFieldStates.waiting_field_name)
async def process_field_name(message: Message, state: FSMContext):
    """Обработка названия поля"""
    await state.update_data(field_name=message.text)
    
    text = "Выберите тип поля:\n"
    text += "1. text - Текст\n"
    text += "2. email - Email\n"
    text += "3. phone - Телефон\n"
    text += "4. number - Число\n"
    text += "5. date - Дата\n"
    text += "6. select - Выбор из списка\n\n"
    text += "Отправьте номер или название типа:"
    
    await message.answer(text)
    await state.set_state(AddFieldStates.waiting_field_type)


@router.message(AddFieldStates.waiting_field_type)
async def process_field_type(message: Message, state: FSMContext):
    """Обработка типа поля"""
    type_map = {
        "1": FieldType.TEXT, "text": FieldType.TEXT,
        "2": FieldType.EMAIL, "email": FieldType.EMAIL,
        "3": FieldType.PHONE, "phone": FieldType.PHONE,
        "4": FieldType.NUMBER, "number": FieldType.NUMBER,
        "5": FieldType.DATE, "date": FieldType.DATE,
        "6": FieldType.SELECT, "select": FieldType.SELECT,
    }
    
    field_type = type_map.get(message.text.lower().strip())
    if not field_type:
        await message.answer("❌ Неверный тип. Выберите от 1 до 6 или название типа.")
        return
    
    await state.update_data(field_type=field_type)
    
    if field_type == FieldType.SELECT:
        await message.answer("Введите варианты выбора через запятую (например: Вариант 1, Вариант 2, Вариант 3):")
        await state.set_state(AddFieldStates.waiting_options)
    else:
        await message.answer("Поле обязательно для заполнения? (да/нет):")
        await state.set_state(AddFieldStates.waiting_required)


@router.message(AddFieldStates.waiting_options)
async def process_field_options(message: Message, state: FSMContext):
    """Обработка вариантов для select"""
    options = [opt.strip() for opt in message.text.split(",") if opt.strip()]
    if not options:
        await message.answer("❌ Нужно указать хотя бы один вариант.")
        return
    
    await state.update_data(options=options)
    await message.answer("Поле обязательно для заполнения? (да/нет):")
    await state.set_state(AddFieldStates.waiting_required)


@router.message(AddFieldStates.waiting_required)
async def process_field_required(message: Message, state: FSMContext, user: User):
    """Обработка обязательности поля"""
    required = message.text.lower().strip() in ["да", "yes", "y", "1", "true"]
    
    data = await state.get_data()
    event_id = data['event_id']
    
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await message.answer("Событие не найдено.")
            await state.clear()
            return
        
        # Определяем порядок (максимальный + 1)
        max_order = db.query(EventField).filter(EventField.event_id == event_id).count()
        
        field = EventField(
            event_id=event_id,
            field_name=data['field_name'],
            field_type=data['field_type'],
            required=required,
            order=max_order,
            options=data.get('options')
        )
        db.add(field)
        db.commit()
        
        await message.answer(f"✅ Поле '{field.field_name}' добавлено к событию '{event.title}'!")
        await state.clear()
    finally:
        db.close()


@router.message(EditEventStates.waiting_photo)
async def process_edit_photo(message: Message, state: FSMContext, user: User):
    """Обработка нового фото при редактировании"""
    data = await state.get_data()
    event_id = data['event_id']
    
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await message.answer("Событие не найдено.")
            await state.clear()
            return
        
        photo_file_id = None
        photo_file_ids = []
        
        if message.text and message.text.strip() == "-":
            # Оставить текущее фото
            pass
        elif message.text and message.text.strip() == "--":
            # Удалить фото
            event.photo_file_id = None
            event.photo_file_ids = None
        elif message.photo:
            # Новое фото
            photo = message.photo[-1]
            photo_file_id = photo.file_id
            photo_file_ids = [photo_file_id]
            event.photo_file_id = photo_file_id
            event.photo_file_ids = photo_file_ids
        
        db.commit()
        db.refresh(event)
        
        await message.answer(f"✅ Событие '{event.title}' обновлено!")
        await state.clear()
        
        # Показываем обновленное событие
        if is_admin(user):
            from bot.keyboards.admin_keyboards import get_event_actions_keyboard
            
            text = f"📅 {event.title}\n\n"
            text += f"📝 Описание: {event.description or 'Нет описания'}\n"
            from utils.timezone import format_event_datetime
            text += f"📆 Дата: {format_event_datetime(event.date_time)}\n"
            text += f"📊 Статус: {event.status.value}\n"
            text += f"👤 Создано: {event.creator.full_name or 'Неизвестно'}\n"
            
            registrations_count = len(event.registrations)
            text += f"📋 Регистраций: {registrations_count}"
            
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
        else:
            from bot.keyboards.assistant_keyboards import get_assistant_event_actions_keyboard
            
            can_edit = can_edit_event(db, user, event_id)
            
            text = f"📅 {event.title}\n\n"
            text += f"📝 Описание: {event.description or 'Нет описания'}\n"
            from utils.timezone import format_event_datetime
            text += f"📆 Дата: {format_event_datetime(event.date_time)}\n"
            text += f"📊 Статус: {event.status.value}\n"
            
            if can_view_registrations(db, user, event_id):
                registrations_count = len(event.registrations)
                text += f"📋 Регистраций: {registrations_count}"
            
            if event.photo_file_id:
                try:
                    await message.answer_photo(
                        photo=event.photo_file_id,
                        caption=text,
                        reply_markup=get_assistant_event_actions_keyboard(event.id, can_edit)
                    )
                    return
                except Exception:
                    pass
            
            await message.answer(
                text,
                reply_markup=get_assistant_event_actions_keyboard(event.id, can_edit)
            )
    finally:
        db.close()

