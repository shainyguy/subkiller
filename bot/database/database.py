"""Управление подключением к БД и сессиями."""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
    AsyncEngine,
)
from bot.database.models import Base
from bot.config import config


engine: AsyncEngine = create_async_engine(
    config.db.url,
    echo=False,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    """Создание всех таблиц."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Получение сессии БД."""
    async with async_session() as session:
        return session