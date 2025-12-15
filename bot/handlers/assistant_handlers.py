from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.models import User, Event, EventStatus, Registration
from bot.keyboards.assistant_keyboards import (
    get_assistant_events_menu,
    get_assistant_event_actions_keyboard
)
from utils.permissions import is_assistant, can_edit_event, can_view_registrations, can_send_notifications, get_user_accessible_events
from database.database import SessionLocal
from datetime import datetime

router = Router()


class CreateDraftStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_date = State()
    waiting_photo = State()


@router.message(F.text == "📅 Мои события")
async def assistant_events_menu(message: Message, user: User):
    """Меню событий для помощника"""
    if not is_assistant(user):
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    await message.answer("Мои события:", reply_markup=get_assistant_events_menu())


@router.message(F.text == "📊 Регистрации")
async def assistant_registrations_menu(message: Message, user: User):
    """Меню регистраций для помощника"""
    if not is_assistant(user):
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    db = SessionLocal()
    try:
        events = get_user_accessible_events(db, user)
        if not events:
            await message.answer("У вас нет доступа ни к одному событию.")
            return
        
        from bot.keyboards.common_keyboards import get_events_list_keyboard
        await message.answer(
            "Выберите событие для просмотра регистраций:",
            reply_markup=get_events_list_keyboard(events, "assistant_registrations")
        )
    finally:
        db.close()


@router.message(F.text == "🔔 Уведомления")
async def assistant_notifications_menu(message: Message, user: User):
    """Меню уведомлений для помощника"""
    if not is_assistant(user):
        await message.answer("У вас нет доступа к этой функции.")
        return
    
    await message.answer("Управление уведомлениями будет реализовано позже.")


@router.callback_query(F.data == "assistant_events_menu")
async def assistant_events_menu_callback(callback: CallbackQuery, user: User):
    """Меню событий для помощника (callback)"""
    if not is_assistant(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    await callback.message.edit_text("Мои события:", reply_markup=get_assistant_events_menu())


@router.callback_query(F.data == "assistant_list_events")
async def assistant_list_events_callback(callback: CallbackQuery, user: User):
    """Список событий помощника"""
    if not is_assistant(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        events = get_user_accessible_events(db, user)
        if not events:
            await callback.message.edit_text("У вас нет доступа ни к одному событию.")
            return
        
        from bot.keyboards.common_keyboards import get_events_list_keyboard
        await callback.message.edit_text(
            "Выберите событие:",
            reply_markup=get_events_list_keyboard(events, "assistant_event")
        )
    finally:
        db.close()


@router.callback_query(F.data.startswith("assistant_event_"))
async def assistant_event_detail(callback: CallbackQuery, user: User):
    """Детали события для помощника"""
    if not is_assistant(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        # Проверяем права доступа
        can_edit = can_edit_event(db, user, event_id)
        can_view = can_view_registrations(db, user, event_id)
        
        if not can_view and not can_edit:
            await callback.answer("У вас нет доступа к этому событию.", show_alert=True)
            return
        
        text = f"📅 {event.title}\n\n"
        text += f"📝 Описание: {event.description or 'Нет описания'}\n"
        from utils.timezone import format_event_datetime
        text += f"📆 Дата: {format_event_datetime(event.date_time)}\n"
        text += f"📊 Статус: {event.status.value}\n"
        
        if can_view:
            registrations_count = len(event.registrations)
            text += f"📋 Регистраций: {registrations_count}"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_assistant_event_actions_keyboard(event.id, can_edit)
        )
    finally:
        db.close()


@router.callback_query(F.data == "assistant_create_draft")
async def assistant_create_draft_start(callback: CallbackQuery, user: User, state: FSMContext):
    """Начало создания черновика"""
    if not is_assistant(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    await callback.message.answer("Создание черновика события.\nВведите название события:")
    await state.set_state(CreateDraftStates.waiting_title)
    await callback.answer()


@router.message(CreateDraftStates.waiting_title)
async def process_draft_title(message: Message, state: FSMContext):
    """Обработка названия черновика"""
    await state.update_data(title=message.text)
    await message.answer("Введите описание события (или отправьте '-' чтобы пропустить):")
    await state.set_state(CreateDraftStates.waiting_description)


@router.message(CreateDraftStates.waiting_description)
async def process_draft_description(message: Message, state: FSMContext):
    """Обработка описания черновика"""
    description = message.text if message.text != "-" else None
    await state.update_data(description=description)
    await message.answer("Введите дату и время события в формате ДД.ММ.ГГГГ ЧЧ:ММ:")
    await state.set_state(CreateDraftStates.waiting_date)


@router.message(CreateDraftStates.waiting_date)
async def process_draft_date(message: Message, state: FSMContext, user: User):
    """Обработка даты черновика"""
    try:
        from utils.timezone import parse_local_datetime
        date_str = message.text.strip()
        date_time = parse_local_datetime(date_str, "%d.%m.%Y %H:%M")
        
        data = await state.get_data()
        db = SessionLocal()
        try:
            event = Event(
                title=data['title'],
                description=data.get('description'),
                date_time=date_time,
                status=EventStatus.DRAFT,
                created_by=user.id
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            
            from utils.timezone import format_event_datetime
            await message.answer(f"✅ Черновик события '{event.title}' создан!\n\n"
                               f"ID: {event.id}\n"
                               f"Дата: {format_event_datetime(event.date_time)}\n\n"
                               f"Черновик отправлен на утверждение администратору.")
            await state.clear()
        finally:
            db.close()
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте формат: ДД.ММ.ГГГГ ЧЧ:ММ\n"
                           "Например: 25.12.2024 18:00")


@router.callback_query(F.data == "assistant_drafts")
async def assistant_drafts(callback: CallbackQuery, user: User):
    """Список черновиков помощника"""
    if not is_assistant(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    db = SessionLocal()
    try:
        drafts = db.query(Event).filter(
            Event.created_by == user.id,
            Event.status == EventStatus.DRAFT
        ).order_by(Event.created_at.desc()).all()
        
        if not drafts:
            await callback.message.edit_text("У вас нет черновиков.")
            return
        
        from bot.keyboards.common_keyboards import get_events_list_keyboard
        await callback.message.edit_text(
            "Мои черновики:",
            reply_markup=get_events_list_keyboard(drafts, "assistant_event")
        )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("assistant_registrations_"))
async def assistant_view_registrations(callback: CallbackQuery, user: User):
    """Просмотр регистраций на событие для помощника"""
    if not is_assistant(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        # Проверяем права на просмотр регистраций
        if not can_view_registrations(db, user, event_id):
            await callback.answer("У вас нет доступа к регистрациям этого события.", show_alert=True)
            return
        
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
        text += f"Всего регистраций: {len(registrations)}\n\n"
        
        for i, reg in enumerate(registrations[:10], 1):
            user_obj = db.query(User).filter(User.telegram_id == reg.user_telegram_id).first()
            user_name = user_obj.full_name if user_obj else f"ID: {reg.user_telegram_id}"
            text += f"{i}. {user_name}\n"
            text += f"   Дата: {reg.created_at.strftime('%d.%m.%Y %H:%M')}\n"
            if reg.data_json:
                for key, value in list(reg.data_json.items())[:3]:
                    text += f"   {key}: {value}\n"
            text += "\n"
        
        if len(registrations) > 10:
            text += f"\n... и еще {len(registrations) - 10} регистраций"
        
        await callback.message.answer(text)
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("assistant_send_notification_"))
async def assistant_send_notification(callback: CallbackQuery, user: User):
    """Отправка уведомления для помощника"""
    if not is_assistant(user):
        await callback.answer("У вас нет доступа.", show_alert=True)
        return
    
    event_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        # Проверяем права на отправку уведомлений
        if not can_send_notifications(db, user, event_id):
            await callback.answer("У вас нет прав на отправку уведомлений для этого события.", show_alert=True)
            return
        
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        # Отправляем уведомление
        from bot.utils.notifications import send_manual_notification
        from aiogram import Bot
        from config import settings
        
        bot = Bot(token=settings.BOT_TOKEN)
        sent_count = await send_manual_notification(db, bot, event)
        await bot.session.close()
        
        await callback.message.answer(
            f"✅ Уведомление отправлено {sent_count} зарегистрированным пользователям!"
        )
        await callback.answer()
    finally:
        db.close()

