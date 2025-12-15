import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from database.database import SessionLocal
from services.notification_service import get_pending_notifications, send_notification
from aiogram import Bot
from config import settings
from utils.timezone import get_utc_now

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()
bot_instance: Bot = None


def set_bot_instance(bot: Bot):
    """Установить экземпляр бота для отправки уведомлений"""
    global bot_instance
    bot_instance = bot


async def check_and_send_notifications():
    """Проверить и отправить запланированные уведомления"""
    if not bot_instance:
        logger.warning("Bot instance not set, skipping notification check")
        return
    
    db = SessionLocal()
    try:
        pending = get_pending_notifications(db)
        
        if not pending:
            return
        
        logger.info(f"Found {len(pending)} pending notifications")
        
        for notification in pending:
            try:
                success = await send_notification_async(db, notification)
                if success:
                    logger.info(f"Notification {notification.id} sent successfully")
                else:
                    logger.warning(f"Failed to send notification {notification.id}")
            except Exception as e:
                logger.error(f"Error sending notification {notification.id}: {e}")
    finally:
        db.close()


async def send_notification_async(db, scheduled_notification):
    """Асинхронная отправка уведомления"""
    try:
        from database.models import Registration, Event, EventNotification
        from bot.handlers.notification_handlers import get_notification_keyboard
        from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
        
        registration = db.query(Registration).filter(
            Registration.id == scheduled_notification.registration_id
        ).first()
        
        if not registration:
            logger.warning(f"Registration {scheduled_notification.registration_id} not found")
            return False
        
        event = db.query(Event).filter(Event.id == scheduled_notification.event_id).first()
        if not event:
            logger.warning(f"Event {scheduled_notification.event_id} not found")
            return False
        
        # Проверяем, нужно ли добавлять кнопки
        include_buttons = True
        event_notif = db.query(EventNotification).filter(
            EventNotification.event_id == event.id,
            EventNotification.enabled == True
        ).first()
        
        if event_notif:
            include_buttons = event_notif.include_buttons
        
        # Формируем сообщение
        from utils.timezone import format_event_datetime
        
        message_text = f"🔔 Напоминание о событии!\n\n"
        message_text += f"📅 {event.title}\n"
        message_text += f"📆 Дата: {format_event_datetime(event.date_time)}\n"
        
        if event.description:
            message_text += f"\n{event.description}\n"
        
        # Отправляем сообщение с кнопками или без
        try:
            if include_buttons:
                await bot_instance.send_message(
                    chat_id=registration.user_telegram_id,
                    text=message_text,
                    reply_markup=get_notification_keyboard(registration.id)
                )
            else:
                await bot_instance.send_message(
                    chat_id=registration.user_telegram_id,
                    text=message_text
                )
            
            # Отмечаем как отправленное
            scheduled_notification.sent = True
            scheduled_notification.sent_at = get_utc_now()
            db.commit()
            
            logger.info(f"Notification {scheduled_notification.id} sent successfully to user {registration.user_telegram_id}")
            return True
            
        except TelegramForbiddenError as e:
            # Пользователь заблокировал бота или удалил диалог
            logger.warning(f"Cannot send notification {scheduled_notification.id} to user {registration.user_telegram_id}: user blocked bot or chat not found. Error: {e}")
            # Отмечаем как отправленное, чтобы не пытаться снова
            scheduled_notification.sent = True
            scheduled_notification.sent_at = get_utc_now()
            db.commit()
            return False
            
        except TelegramBadRequest as e:
            # Другие ошибки Telegram API (неверный chat_id и т.д.)
            logger.error(f"Telegram API error sending notification {scheduled_notification.id} to user {registration.user_telegram_id}: {e}")
            # Отмечаем как отправленное, чтобы не пытаться снова
            scheduled_notification.sent = True
            scheduled_notification.sent_at = get_utc_now()
            db.commit()
            return False
            
    except Exception as e:
        logger.error(f"Unexpected error sending notification {scheduled_notification.id}: {e}", exc_info=True)
        return False


def start_scheduler():
    """Запустить планировщик"""
    scheduler.add_job(
        check_and_send_notifications,
        trigger=IntervalTrigger(seconds=30),  # Проверяем каждые 30 секунд
        id='check_notifications',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Notification scheduler started")


def stop_scheduler():
    """Остановить планировщик"""
    scheduler.shutdown()
    logger.info("Notification scheduler stopped")

