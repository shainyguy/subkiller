"""Мидлвар для ограничения частоты запросов."""

from typing import Any, Awaitable, Callable, Dict, MutableMapping
from datetime import datetime, timedelta
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery


class ThrottlingMiddleware(BaseMiddleware):
    """Ограничение: 1 сообщение в секунду."""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self.user_last_request: MutableMapping[int, datetime] = {}

    async def __call__(
        self,
        handler: Callable[
            [TelegramObject, Dict[str, Any]], Awaitable[Any]
        ],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None

        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            now = datetime.utcnow()
            last = self.user_last_request.get(user_id)

            if last and (now - last) < timedelta(
                seconds=self.rate_limit
            ):
                return  # Игнорируем слишком частые запросы

            self.user_last_request[user_id] = now

        return await handler(event, data)