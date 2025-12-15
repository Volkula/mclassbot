from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional
import zoneinfo


class Settings(BaseSettings):
    # Telegram Bot
    BOT_TOKEN: Optional[str] = None
    
    # Telegram WebApp
    WEBAPP_URL: Optional[str] = None
    
    # Database
    DATABASE_URL: str = "sqlite:///./event_registration.db"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    # Admin
    ADMIN_USER_IDS: list[int] = []
    
    # Timezone
    TIMEZONE: str = "Europe/Moscow"  # GMT+3 по умолчанию
    
    @property
    def timezone(self):
        """Возвращает объект timezone"""
        try:
            return zoneinfo.ZoneInfo(self.TIMEZONE)
        except zoneinfo.ZoneInfoNotFoundError:
            # Fallback на UTC+3 если указан неверный часовой пояс
            from datetime import timedelta, timezone
            return timezone(timedelta(hours=3))
    
    @field_validator('ADMIN_USER_IDS', mode='before')
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if not v or v.strip() == "":
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        if isinstance(v, int):
            return [v]
        return []
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

