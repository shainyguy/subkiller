"""Сервис поиска альтернатив подписок."""

import logging
from typing import Optional

from bot.config import ALTERNATIVES_DB
from bot.services.gigachat_service import gigachat_service

logger = logging.getLogger(__name__)


async def find_alternatives(
    service_name: str,
    price: float,
    category: str,
    use_ai: bool = False,
) -> list[dict]:
    """
    Поиск альтернатив: сначала локальная база,
    потом AI (если Premium).
    """
    # 1. Локальная база
    local = ALTERNATIVES_DB.get(service_name, [])
    if local:
        return local

    # 2. Проверяем похожие имена
    for key in ALTERNATIVES_DB:
        if key.lower() in service_name.lower():
            return ALTERNATIVES_DB[key]
        if service_name.lower() in key.lower():
            return ALTERNATIVES_DB[key]

    # 3. AI-поиск (Premium)
    if use_ai:
        try:
            ai_result = await gigachat_service.find_alternatives(
                service_name=service_name,
                price=price,
                category=category,
            )
            if ai_result:
                return ai_result
        except Exception as e:
            logger.error(f"AI alt search error: {e}")

    return []