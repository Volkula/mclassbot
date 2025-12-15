from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database.models import User, Registration, Event, UserEventPermission
from database.database import SessionLocal
from utils.permissions import is_admin, can_send_notifications
from aiogram import Bot
from config import settings
from sqlalchemy.orm import Session

router = Router()


@router.callback_query(F.data.startswith("confirm_participation_"))
async def confirm_participation(callback: CallbackQuery, user: User):
    """Подтверждение участия"""
    registration_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        registration = db.query(Registration).filter(Registration.id == registration_id).first()
        if not registration:
            await callback.answer("Регистрация не найдена.", show_alert=True)
            return
        
        if registration.user_telegram_id != user.telegram_id:
            await callback.answer("Это не ваша регистрация.", show_alert=True)
            return
        
        registration.confirmed = True
        db.commit()
        
        await callback.answer("✅ Вы подтвердили участие!", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        
        # Уведомляем организаторов
        event = db.query(Event).filter(Event.id == registration.event_id).first()
        if event:
            await notify_organizers_about_response(db, event, registration, "подтвердил участие")
    finally:
        db.close()


@router.callback_query(F.data.startswith("decline_participation_"))
async def decline_participation(callback: CallbackQuery, user: User):
    """Отказ от участия"""
    registration_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        registration = db.query(Registration).filter(Registration.id == registration_id).first()
        if not registration:
            await callback.answer("Регистрация не найдена.", show_alert=True)
            return
        
        if registration.user_telegram_id != user.telegram_id:
            await callback.answer("Это не ваша регистрация.", show_alert=True)
            return
        
        registration.confirmed = False
        db.commit()
        
        await callback.answer("❌ Вы отказались от участия.", show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        
        # Уведомляем организаторов
        event = db.query(Event).filter(Event.id == registration.event_id).first()
        if event:
            await notify_organizers_about_response(db, event, registration, "отказался от участия")
    finally:
        db.close()


@router.callback_query(F.data.startswith("contact_me_"))
async def contact_me(callback: CallbackQuery, user: User):
    """Запрос на связь"""
    registration_id = int(callback.data.split("_")[-1])
    db = SessionLocal()
    try:
        registration = db.query(Registration).filter(Registration.id == registration_id).first()
        if not registration:
            await callback.answer("Регистрация не найдена.", show_alert=True)
            return
        
        if registration.user_telegram_id != user.telegram_id:
            await callback.answer("Это не ваша регистрация.", show_alert=True)
            return
        
        event = db.query(Event).filter(Event.id == registration.event_id).first()
        if not event:
            await callback.answer("Событие не найдено.", show_alert=True)
            return
        
        # Получаем список получателей уведомлений
        from database.models import EventNotification
        recipient_ids = []
        
        event_notif = db.query(EventNotification).filter(
            EventNotification.event_id == event.id,
            EventNotification.enabled == True
        ).first()
        
        if event_notif and event_notif.notification_recipients:
            recipient_ids = event_notif.notification_recipients
        else:
            # По умолчанию - автор и помощники
            if event.created_by:
                recipient_ids.append(event.created_by)
            
            permissions = db.query(UserEventPermission).filter(
                UserEventPermission.event_id == event.id,
                UserEventPermission.can_send_notifications == True
            ).all()
            recipient_ids.extend([p.user_id for p in permissions])
        
        # Убираем дубликаты
        recipient_ids = list(set(recipient_ids))
        
        if not recipient_ids:
            await callback.answer("Нет ответственных за событие.", show_alert=True)
            return
        
        # Формируем сообщение
        contact_text = f"📞 Запрос на связь\n\n"
        contact_text += f"Событие: {event.title}\n"
        contact_text += f"Пользователь: {user.full_name or 'Без имени'}\n"
        contact_text += f"Telegram ID: {user.telegram_id}\n"
        if user.username:
            contact_text += f"Username: @{user.username}\n"
        contact_text += f"\nПользователь просит связаться с ним."
        
        # Отправляем сообщение помощникам
        bot = Bot(token=settings.BOT_TOKEN)
        sent_count = 0
        for recipient_id in recipient_ids:
            recipient = db.query(User).filter(User.id == recipient_id).first()
            if recipient:
                try:
                    await bot.send_message(
                        chat_id=recipient.telegram_id,
                        text=contact_text
                    )
                    sent_count += 1
                except Exception as e:
                    print(f"Ошибка отправки сообщения: {e}")
        
        await bot.session.close()
        
        await callback.answer(f"✅ Ваш запрос отправлен {sent_count} организатору(ам)!", show_alert=True)
    finally:
        db.close()


async def notify_organizers_about_response(db: Session, event: Event, registration: Registration, action: str):
    """Уведомить организаторов о ответе пользователя"""
    # Получаем список получателей уведомлений
    recipient_ids = []
    
    # Проверяем настройки уведомлений события
    from database.models import EventNotification
    event_notif = db.query(EventNotification).filter(
        EventNotification.event_id == event.id,
        EventNotification.enabled == True
    ).first()
    
    if event_notif and event_notif.notification_recipients:
        recipient_ids = event_notif.notification_recipients
    else:
        # По умолчанию - автор и помощники
        if event.created_by:
            recipient_ids.append(event.created_by)
        
        permissions = db.query(UserEventPermission).filter(
            UserEventPermission.event_id == event.id,
            UserEventPermission.can_send_notifications == True
        ).all()
        recipient_ids.extend([p.user_id for p in permissions])
    
    recipient_ids = list(set(recipient_ids))
    
    if not recipient_ids:
        return
    
    user = db.query(User).filter(User.telegram_id == registration.user_telegram_id).first()
    if not user:
        return
    
    text = f"📢 Обновление регистрации\n\n"
    text += f"Событие: {event.title}\n"
    text += f"Пользователь: {user.full_name or 'Без имени'}\n"
    text += f"Действие: {action}"
    
    bot = Bot(token=settings.BOT_TOKEN)
    for recipient_id in recipient_ids:
        recipient = db.query(User).filter(User.id == recipient_id).first()
        if recipient:
            try:
                await bot.send_message(
                    chat_id=recipient.telegram_id,
                    text=text
                )
            except Exception:
                pass
    
    await bot.session.close()


def get_notification_keyboard(registration_id: int) -> InlineKeyboardMarkup:
    """Создать клавиатуру для уведомления"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ Я подтверждаю участие",
                callback_data=f"confirm_participation_{registration_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Я не смогу присутствовать",
                callback_data=f"decline_participation_{registration_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="📞 Свяжитесь со мной",
                callback_data=f"contact_me_{registration_id}"
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

