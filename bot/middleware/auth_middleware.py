from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TelegramUser
from sqlalchemy.orm import Session
from database.database import SessionLocal
from database.models import User, UserRole
from config import settings


class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки авторизации и получения пользователя из БД"""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Получаем пользователя из события
        telegram_user: TelegramUser = data.get("event_from_user")
        
        if not telegram_user:
            return await handler(event, data)
        
        # Получаем или создаем пользователя в БД
        db: Session = SessionLocal()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_user.id).first()
            
            if not user:
                # Создаем нового пользователя
                # Проверяем, является ли он админом по настройкам
                is_admin = telegram_user.id in settings.ADMIN_USER_IDS
                role = UserRole.ADMIN if is_admin else UserRole.USER
                
                user = User(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    full_name=telegram_user.full_name or f"{telegram_user.first_name} {telegram_user.last_name or ''}".strip(),
                    role=role
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                # Обновляем информацию о пользователе
                user.username = telegram_user.username
                user.full_name = telegram_user.full_name or f"{telegram_user.first_name} {telegram_user.last_name or ''}".strip()
                
                # Обновляем роль, если пользователь в списке админов
                if telegram_user.id in settings.ADMIN_USER_IDS:
                    user.role = UserRole.ADMIN
                
                db.commit()
            
            # Добавляем пользователя в data для использования в handlers
            data["user"] = user
            data["db"] = db
            
        except Exception as e:
            db.rollback()
            raise e
        
        try:
            result = await handler(event, data)
        finally:
            db.close()
        
        return result

