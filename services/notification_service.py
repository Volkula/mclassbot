from sqlalchemy.orm import Session
from database.models import (
    Event, Registration, ScheduledNotification, NotificationTemplate,
    EventNotification, User
)
from datetime import datetime, timedelta
from typing import List, Optional
import logging
from utils.timezone import get_local_now, get_utc_now, local_to_utc, utc_to_local
import zoneinfo

logger = logging.getLogger(__name__)


def create_scheduled_notifications_for_event(db: Session, event: Event):
    """Создать запланированные уведомления для всех регистраций на событие"""
    # Если у события нет даты/времени, уведомления создавать нельзя
    if not event.date_time:
        logger.warning(f"Event {event.id} has no date_time, skipping notification scheduling")
        return

    # Приводим время события к UTC-aware, затем к локальному времени
    event_dt = event.date_time
    if event_dt.tzinfo is None:
        # В БД храним UTC без tzinfo
        event_dt_utc = event_dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
    else:
        event_dt_utc = event_dt.astimezone(zoneinfo.ZoneInfo("UTC"))

    event_dt_local = utc_to_local(event_dt_utc)

    # Получаем настройки уведомлений для события
    event_notifications = db.query(EventNotification).filter(
        EventNotification.event_id == event.id,
        EventNotification.enabled == True
    ).all()
    
    if not event_notifications:
        logger.info(f"No enabled notifications found for event {event.id}")
        return
    
    # Получаем все регистрации на событие
    registrations = db.query(Registration).filter(Registration.event_id == event.id).all()
    
    logger.info(
        f"[create_scheduled_notifications_for_event] event_id={event.id}, "
        f"event_dt_local={event_dt_local}, "
        f"notifications={len(event_notifications)}, registrations={len(registrations)}"
    )
    
    for registration in registrations:
        for event_notif in event_notifications:
            notification_time_local = None

            # Определяем локальное время уведомления
            if event_notif.custom_time is not None:
                # Кастомное время в минутах относительно времени события (локального)
                notification_time_local = event_dt_local - timedelta(minutes=event_notif.custom_time)
            elif event_notif.template_id:
                template = db.query(NotificationTemplate).filter(
                    NotificationTemplate.id == event_notif.template_id
                ).first()
                if template:
                    if template.absolute_datetime:
                        # absolute_datetime хранится в UTC (naive), приводим к локальному времени
                        abs_dt = template.absolute_datetime
                        if abs_dt.tzinfo is None:
                            abs_dt_utc = abs_dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                        else:
                            abs_dt_utc = abs_dt.astimezone(zoneinfo.ZoneInfo("UTC"))
                        notification_time_local = utc_to_local(abs_dt_utc)
                    elif template.time_before_event:
                        # Время до события в минутах (от локального времени события)
                        notification_time_local = event_dt_local - timedelta(minutes=template.time_before_event)
                else:
                    logger.warning(
                        f"[create_scheduled_notifications_for_event] template id {event_notif.template_id} "
                        f"not found for event {event.id}"
                    )
                    continue
            else:
                continue

            if not notification_time_local:
                logger.warning(
                    f"[create_scheduled_notifications_for_event] got empty notification_time_local "
                    f"for event_id={event.id}, registration_id={registration.id}, notif_id={event_notif.id}"
                )
                continue

            # Переводим локальное время уведомления в UTC для хранения
            notification_time_utc = local_to_utc(notification_time_local)

            # Проверяем, не создано ли уже такое уведомление
            existing = db.query(ScheduledNotification).filter(
                ScheduledNotification.event_id == event.id,
                ScheduledNotification.registration_id == registration.id,
                ScheduledNotification.scheduled_time == notification_time_utc
            ).first()
            
            if existing:
                logger.info(
                    f"[create_scheduled_notifications_for_event] notification already exists "
                    f"for event_id={event.id}, registration_id={registration.id}, "
                    f"time_utc={notification_time_utc}"
                )
                continue

            if not existing:
                # Создаем уведомление, если время еще не прошло (или прошло не более чем на 1 час - для тестирования)
                local_now = get_local_now()
                time_diff = (notification_time_local - local_now).total_seconds() / 60  # в минутах
                if time_diff > -60:  # Если уведомление не более чем на час в прошлом
                    scheduled = ScheduledNotification(
                        event_id=event.id,
                        registration_id=registration.id,
                        notification_type='template' if event_notif.template_id else 'custom',
                        scheduled_time=notification_time_utc
                    )
                    db.add(scheduled)
                    logger.info(
                        f"Created scheduled notification for registration {registration.id}, "
                        f"event {event.id}, local_time: {notification_time_local}, "
                        f"time_diff: {time_diff:.1f} min"
                    )
                else:
                    logger.warning(
                        f"[create_scheduled_notifications_for_event] Skipping notification for "
                        f"registration {registration.id} - time {notification_time_local} "
                        f"is too far in the past ({time_diff:.1f} min)"
                    )
    
    db.commit()


def send_notification(db: Session, scheduled_notification: ScheduledNotification, bot) -> bool:
    """Отправить уведомление пользователю"""
    try:
        registration = db.query(Registration).filter(
            Registration.id == scheduled_notification.registration_id
        ).first()
        
        if not registration:
            return False
        
        event = db.query(Event).filter(Event.id == scheduled_notification.event_id).first()
        if not event:
            return False
        
        # Формируем сообщение
        from utils.timezone import format_event_datetime
        
        message_text = f"🔔 Напоминание о событии!\n\n"
        message_text += f"📅 {event.title}\n"
        message_text += f"📆 Дата: {format_event_datetime(event.date_time)}\n"
        
        if event.description:
            message_text += f"\n{event.description}\n"
        
        # Отправляем сообщение
        import asyncio
        asyncio.create_task(
            bot.send_message(
                chat_id=registration.user_telegram_id,
                text=message_text
            )
        )
        
        # Отмечаем как отправленное
        scheduled_notification.sent = True
        scheduled_notification.sent_at = get_utc_now()
        db.commit()
        
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")
        return False


def get_pending_notifications(db: Session) -> List[ScheduledNotification]:
    """Получить список уведомлений, которые нужно отправить"""
    now_utc = get_utc_now()
    notifications = db.query(ScheduledNotification).filter(
        ScheduledNotification.sent == False,
        ScheduledNotification.scheduled_time <= now_utc
    ).all()
    
    local_now = get_local_now()
    logger.info(f"Found {len(notifications)} pending notifications at {local_now} (local) / {now_utc} (UTC)")
    return notifications


def create_notification_template(
    db: Session,
    name: str,
    time_before_event: int,
    message_template: str
) -> NotificationTemplate:
    """Создать шаблон уведомления"""
    template = NotificationTemplate(
        name=name,
        time_before_event=time_before_event,
        message_template=message_template
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template

