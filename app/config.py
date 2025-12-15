from pydantic_settings import BaseSettings
from typing import Optional, List
import zoneinfo
import json


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
    
    # Admin (сырой формат из .env, парсим сами, чтобы не падать на JSON)
    ADMIN_USER_IDS: Optional[str] = None
    
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
    
    @property
    def admin_ids(self) -> List[int]:
        """
        Возвращает список ID админов.
        Поддерживает форматы:
        - CSV:  "111,222"
        - JSON: "[111, 222]"
        """
        raw = self.ADMIN_USER_IDS
        if not raw:
            return []

        # Если вдруг пришел JSON-список
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [int(str(x).strip()) for x in data if str(x).strip().isdigit()]
        except Exception:
            pass

        # Обычная строка с id через запятую
        return [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

