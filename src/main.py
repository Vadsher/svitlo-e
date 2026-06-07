"""Application entry point."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from src.config import BOT_TOKEN
from src.logger import setup_logging
from src.handlers import router
from src.monitor import run_monitoring
from src.scheduler import setup_scheduler

async def main():
    """Initialize bot, dispatcher, and start background tasks."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Initializing bot and dispatcher...")
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    # Register bot commands so the '/' menu appears in Telegram
    await bot.set_my_commands([
        BotCommand(command="start", description="Початок роботи"),
        BotCommand(command="add", description="Додати адресу для моніторингу"),
        BotCommand(command="list", description="Список моніторингових адрес"),
        BotCommand(command="delete", description="Видалити адресу з моніторингу"),
        BotCommand(command="settings", description="Налаштування чату та звітів"),
        BotCommand(command="help", description="Довідка"),
        BotCommand(command="about", description="Про бота"),
    ])
    
    # Start the monitoring task in the background
    asyncio.create_task(run_monitoring(bot))
    
    logger.info("Starting scheduler...")
    scheduler = setup_scheduler(bot)
    scheduler.start()
    
    logger.info("Starting Telegram polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
