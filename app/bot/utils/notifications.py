from sqlalchemy.orm import Session
from typing import Optional
from database.models import Event, Registration, User
from services.notification_service import create_scheduled_notifications_for_event
from aiogram import Bot


async def send_manual_notification(
    db: Session,
    bot: Bot,
    event: Event,
    message_text: Optional[str] = None,
    include_buttons: bool = True
):
    """Отправить уведомление вручную всем зарегистрированным пользователям"""
    from database.models import EventNotification
    from bot.handlers.notification_handlers import get_notification_keyboard
    
    registrations = db.query(Registration).filter(Registration.event_id == event.id).all()
    
    if not registrations:
        return 0
    
    # Проверяем настройки события
    event_notif = db.query(EventNotification).filter(
        EventNotification.event_id == event.id,
        EventNotification.enabled == True
    ).first()
    
    if event_notif:
        include_buttons = event_notif.include_buttons
    
    from utils.timezone import format_event_datetime
    text = message_text or f"🔔 Уведомление о событии!\n\n📅 {event.title}\n📆 Дата: {format_event_datetime(event.date_time)}"
    
    sent_count = 0
    for registration in registrations:
        try:
            if include_buttons:
                await bot.send_message(
                    chat_id=registration.user_telegram_id,
                    text=text,
                    reply_markup=get_notification_keyboard(registration.id)
                )
            else:
                await bot.send_message(
                    chat_id=registration.user_telegram_id,
                    text=text
                )
            sent_count += 1
        except Exception as e:
            print(f"Ошибка отправки уведомления пользователю {registration.user_telegram_id}: {e}")
    
    return sent_count

