from sqlalchemy.orm import Session
from database.models import User, UserRole, Event, UserEventPermission
from typing import Optional


def is_admin(user: User) -> bool:
    """Проверка, является ли пользователь админом"""
    return user.role == UserRole.ADMIN


def is_assistant(user: User) -> bool:
    """Проверка, является ли пользователь помощником"""
    return user.role == UserRole.ASSISTANT


def can_edit_event(db: Session, user: User, event_id: int) -> bool:
    """Проверка права на редактирование события"""
    if is_admin(user):
        return True
    
    if not is_assistant(user):
        return False
    
    # Проверяем права помощника на конкретное событие
    permission = db.query(UserEventPermission).filter(
        UserEventPermission.user_id == user.id,
        UserEventPermission.event_id == event_id,
        UserEventPermission.can_edit == True
    ).first()
    
    return permission is not None


def can_view_registrations(db: Session, user: User, event_id: int) -> bool:
    """Проверка права на просмотр регистраций"""
    if is_admin(user):
        return True
    
    if not is_assistant(user):
        return False
    
    # Проверяем права помощника на конкретное событие
    permission = db.query(UserEventPermission).filter(
        UserEventPermission.user_id == user.id,
        UserEventPermission.event_id == event_id,
        UserEventPermission.can_view_registrations == True
    ).first()
    
    return permission is not None


def can_send_notifications(db: Session, user: User, event_id: int) -> bool:
    """Проверка права на отправку уведомлений"""
    if is_admin(user):
        return True
    
    if not is_assistant(user):
        return False
    
    # Проверяем права помощника на конкретное событие
    permission = db.query(UserEventPermission).filter(
        UserEventPermission.user_id == user.id,
        UserEventPermission.event_id == event_id,
        UserEventPermission.can_send_notifications == True
    ).first()
    
    return permission is not None


def get_user_accessible_events(db: Session, user: User) -> list[Event]:
    """Получить список событий, к которым у пользователя есть доступ"""
    if is_admin(user):
        return db.query(Event).all()
    
    if not is_assistant(user):
        return []
    
    # Получаем события, на которые у помощника есть права
    permissions = db.query(UserEventPermission).filter(
        UserEventPermission.user_id == user.id
    ).all()
    
    event_ids = [p.event_id for p in permissions]
    return db.query(Event).filter(Event.id.in_(event_ids)).all() if event_ids else []

