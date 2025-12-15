import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from bot.middleware.auth_middleware import AuthMiddleware
from bot.handlers import common_handlers, admin_handlers, assistant_handlers, event_management, permissions_handlers, settings_handlers, notification_handlers, user_handlers
from database.database import init_db
from services.scheduler import start_scheduler, set_bot_instance

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Основная функция запуска бота"""
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен! Укажите его в файле .env")
        return
    
    # Инициализация БД
    init_db()
    logger.info("База данных инициализирована")
    
    # Создание бота и диспетчера
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Устанавливаем бот для планировщика уведомлений
    set_bot_instance(bot)
    
    # Запускаем планировщик уведомлений
    start_scheduler()
    logger.info("Планировщик уведомлений запущен")
    
    # Регистрация middleware
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    
    # Регистрация роутеров
    dp.include_router(common_handlers.router)
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(assistant_handlers.router)
    dp.include_router(event_management.router)
    dp.include_router(permissions_handlers.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(notification_handlers.router)
    
    logger.info("Бот запущен")
    
    # Запуск polling
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")

