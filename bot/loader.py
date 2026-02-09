"""Инициализация бота и диспетчера."""

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import config

bot = Bot(
    token=config.bot.token,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    ),
)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)