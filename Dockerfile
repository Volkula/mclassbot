FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные зависимости (при необходимости можно расширить)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Копируем исходный код
COPY . /app

# По умолчанию ожидаем .env с переменными окружения (BOT_TOKEN, DATABASE_URL и т.д.)

# Открываем порт для FastAPI (если используется)
EXPOSE 8000

# Запускаем скрипт, который поднимает и бота, и API
CMD ["bash", "run.sh"]


