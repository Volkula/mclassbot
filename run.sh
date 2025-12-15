#!/bin/bash

# Скрипт для запуска приложения

# Активация виртуального окружения
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Запуск бота в фоне
python -m bot.main &
BOT_PID=$!

# Запуск API сервера
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

echo "Бот запущен (PID: $BOT_PID)"
echo "API запущен (PID: $API_PID)"
echo "Для остановки нажмите Ctrl+C"

# Ожидание завершения
wait

