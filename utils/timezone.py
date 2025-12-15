"""Утилиты для работы с часовым поясом"""
from datetime import datetime
import zoneinfo
from config import settings


def get_local_now() -> datetime:
    """Получить текущее время в локальном часовом поясе"""
    return datetime.now(settings.timezone)


def get_utc_now() -> datetime:
    """Получить текущее время в UTC"""
    return datetime.utcnow()


def local_to_utc(local_dt: datetime) -> datetime:
    """Конвертировать локальное время в UTC"""
    if local_dt.tzinfo is None:
        # Если время без часового пояса, считаем его локальным
        local_dt = local_dt.replace(tzinfo=settings.timezone)
    return local_dt.astimezone(zoneinfo.ZoneInfo("UTC")).replace(tzinfo=None)


def utc_to_local(utc_dt: datetime) -> datetime:
    """Конвертировать UTC время в локальное (возвращает aware datetime)"""
    if utc_dt.tzinfo is None:
        # Если время без часового пояса, считаем его UTC
        utc_dt = utc_dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
    return utc_dt.astimezone(settings.timezone)


def parse_local_datetime(datetime_str: str, format_str: str = "%d.%m.%Y %H:%M") -> datetime:
    """Парсить строку даты/времени как локальное время и конвертировать в UTC для хранения"""
    dt = datetime.strptime(datetime_str, format_str)
    # Считаем, что введенное время - это локальное время, конвертируем в UTC
    local_dt = dt.replace(tzinfo=settings.timezone)
    return local_to_utc(local_dt)


def format_event_datetime(utc_dt: datetime, format_str: str = "%d.%m.%Y %H:%M") -> str:
    """Форматировать дату события из UTC в локальное время для отображения"""
    if utc_dt is None:
        return ""
    local_dt = utc_to_local(utc_dt)
    return local_dt.strftime(format_str)

