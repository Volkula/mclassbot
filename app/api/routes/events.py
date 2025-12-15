from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database.database import get_db
from database.models import Event, EventStatus, EventField, FieldType
from api.models.event import EventResponse, EventListResponse
from typing import List
from config import settings
from aiogram import Bot

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/", response_model=EventListResponse)
async def get_active_events(db: Session = Depends(get_db)):
    """Получить список активных событий"""
    events = db.query(Event).filter(
        Event.status.in_([EventStatus.APPROVED, EventStatus.ACTIVE])
    ).order_by(Event.date_time.asc()).all()
    
    # Логирование для отладки
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Найдено событий: {len(events)}")
    for event in events:
        logger.info(f"Событие: {event.id} - {event.title} - {event.status.value}")
    
    return EventListResponse(events=[
            EventResponse(
                id=event.id,
                title=event.title,
                description=event.description,
                date_time=event.date_time,
                status=event.status.value,
                photo_file_id=event.photo_file_id,
                fields=[
                    {
                        "id": field.id,
                        "field_name": field.field_name,
                        "field_type": field.field_type.value,
                        "required": field.required,
                        "order": field.order,
                        "options": field.options
                    }
                    for field in sorted(event.fields, key=lambda x: x.order)
                ]
            )
            for event in events
        ])


@router.get("/{event_id}/photo")
async def get_event_photo(event_id: int, db: Session = Depends(get_db)):
    """Получить фото события (редирект на Telegram файл)"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event or not event.photo_file_id:
        raise HTTPException(status_code=404, detail="Фото не найдено")
    
    if event.status not in [EventStatus.APPROVED, EventStatus.ACTIVE]:
        raise HTTPException(status_code=403, detail="Событие недоступно")
    
    # Получаем URL файла через Telegram Bot API
    try:
        bot = Bot(token=settings.BOT_TOKEN)
        file = await bot.get_file(event.photo_file_id)
        file_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file.file_path}"
        await bot.session.close()
        return RedirectResponse(url=file_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения фото: {str(e)}")


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: int, db: Session = Depends(get_db)):
    """Получить детали события"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    
    if event.status not in [EventStatus.APPROVED, EventStatus.ACTIVE]:
        raise HTTPException(status_code=403, detail="Событие недоступно")
    
    return EventResponse(
        id=event.id,
        title=event.title,
        description=event.description,
        date_time=event.date_time,
        status=event.status.value,
        photo_file_id=event.photo_file_id,
        fields=[
            {
                "id": field.id,
                "field_name": field.field_name,
                "field_type": field.field_type.value,
                "required": field.required,
                "order": field.order,
                "options": field.options
            }
            for field in sorted(event.fields, key=lambda x: x.order)
        ]
    )

