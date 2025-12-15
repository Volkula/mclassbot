import hmac
import hashlib
import json
from typing import Optional, Dict
from urllib.parse import parse_qsl
from config import settings


def validate_telegram_webapp_data(init_data: str) -> Optional[Dict]:
    """
    Валидация данных от Telegram WebApp
    
    Args:
        init_data: Строка initData от Telegram WebApp
        
    Returns:
        Dict с данными пользователя или None если валидация не прошла
    """
    try:
        # Парсим init_data
        parsed_data = dict(parse_qsl(init_data))
        
        # Извлекаем hash и проверяем его наличие
        received_hash = parsed_data.pop('hash', None)
        if not received_hash:
            return None
        
        # Создаем строку для проверки
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        
        # Вычисляем секретный ключ
        secret_key = hmac.new(
            "WebAppData".encode(),
            settings.BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()
        
        # Вычисляем hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Проверяем hash
        if calculated_hash != received_hash:
            return None
        
        # Проверяем время (auth_date не должен быть старше 24 часов)
        import time
        auth_date = int(parsed_data.get('auth_date', 0))
        if time.time() - auth_date > 86400:  # 24 часа
            return None
        
        # Парсим user данные
        user_data = json.loads(parsed_data.get('user', '{}'))
        
        return {
            'id': user_data.get('id'),
            'first_name': user_data.get('first_name'),
            'last_name': user_data.get('last_name'),
            'username': user_data.get('username'),
            'language_code': user_data.get('language_code'),
        }
    except Exception as e:
        print(f"Ошибка валидации: {e}")
        return None

