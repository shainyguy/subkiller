"""Точка входа — запуск бота и webapp."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from aiogram.types import BotCommand
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.loader import bot, dp
from bot.database import init_db
from bot.handlers import setup_routers
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.config import config

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def set_bot_commands():
    """Установка команд бота."""
    commands = [
        BotCommand(command="start", description="🚀 Запуск бота"),
        BotCommand(command="menu", description="📱 Главное меню"),
        BotCommand(command="add", description="➕ Добавить подписку"),
        BotCommand(command="subs", description="📋 Мои подписки"),
        BotCommand(command="pain", description="💀 Счётчик боли"),
        BotCommand(command="report", description="📊 Отчёт"),
        BotCommand(command="top", description="🏆 Рейтинг"),
        BotCommand(command="ref", description="👥 Пригласить друга"),
        BotCommand(command="premium", description="⭐ Premium"),
        BotCommand(command="help", description="❓ Помощь"),
    ]
    await bot.set_my_commands(commands)


def setup_scheduler() -> AsyncIOScheduler:
    """Настройка планировщика задач."""
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    # Проверка уведомлений каждый час
    from bot.services.notification_service import (
        check_and_send_notifications
    )
    scheduler.add_job(
        check_and_send_notifications,
        "interval",
        hours=1,
        args=[bot],
    )

    # Еженедельный отчёт — каждый понедельник в 10:00
    from bot.handlers.weekly_report import (
        send_weekly_reports
    )
    scheduler.add_job(
        send_weekly_reports,
        "cron",
        day_of_week="mon",
        hour=10,
        minute=0,
        args=[bot],
    )

    # Обновление social proof каждые 30 минут
    from bot.handlers.social_proof import (
        generate_social_proof
    )
    scheduler.add_job(
        generate_social_proof,
        "interval",
        minutes=30,
    )

    return scheduler


async def on_startup():
    """Действия при запуске."""
    logger.info("Инициализация базы данных...")
    await init_db()

    logger.info("Установка команд бота...")
    await set_bot_commands()

    logger.info("Запуск планировщика...")
    scheduler = setup_scheduler()
    scheduler.start()

    logger.info("✅ SubKiller Bot запущен!")


async def on_shutdown():
    """Действия при остановке."""
    logger.info("🛑 SubKiller Bot остановлен.")
    await bot.session.close()


async def start_bot():
    """Запуск бота."""
    # Подключаем мидлвари
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5))
    dp.callback_query.middleware(
        ThrottlingMiddleware(rate_limit=0.3)
    )

    # Подключаем роутеры
    main_router = setup_routers()
    dp.include_router(main_router)

    # Запуск
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def start_webapp():
    """Запуск FastAPI webapp."""
    import uvicorn
    from webapp.app import app

    uvicorn_config = uvicorn.Config(
        app,
        host=config.webapp.host,
        port=config.webapp.port,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)
    await server.serve()


async def main():
    """Запуск бота и webapp параллельно."""
    await asyncio.gather(
        start_bot(),
        start_webapp(),
    )


if __name__ == "__main__":
    asyncio.run(main())