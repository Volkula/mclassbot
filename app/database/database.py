from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import settings
import os
from pathlib import Path

# Для SQLite создаем папку для БД, если её нет
if "sqlite" in settings.DATABASE_URL:
    # Извлекаем путь к файлу из DATABASE_URL (например, sqlite:///./data/event_registration.db -> ./data/event_registration.db)
    db_path = settings.DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
    if db_path and not db_path.startswith(":memory:"):
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Инициализация БД - создание всех таблиц"""
    from database.models import Base
    Base.metadata.create_all(bind=engine)

