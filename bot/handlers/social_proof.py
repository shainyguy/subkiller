"""📢 Social Proof — социальное доказательство."""

import logging
import random
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, func, desc

from bot.database import (
    async_session, SocialProofEvent, GlobalStats, User,
)
from bot.utils.helpers import format_money
from bot.keyboards.inline import back_to_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()

# Буфер последних событий для показа
_recent_events_cache: list[dict] = []
_cache_updated_at: float = 0


async def generate_social_proof():
    """
    Обновление кэша social proof.
    Вызывается планировщиком каждые 30 минут.
    """
    global _recent_events_cache, _cache_updated_at

    async with async_session() as session:
        # Последние 20 событий за последние 24 часа
        cutoff = datetime.utcnow() - timedelta(hours=24)
        result = await session.execute(
            select(SocialProofEvent)
            .where(SocialProofEvent.created_at >= cutoff)
            .order_by(desc(SocialProofEvent.created_at))
            .limit(20)
        )
        events = list(result.scalars().all())

    cache = []
    for e in events:
        type_emoji = {
            "saved": "💰",
            "found_subs": "🔍",
            "cancelled": "✂️",
        }
        emoji = type_emoji.get(e.event_type, "📢")

        cache.append({
            "emoji": emoji,
            "username": e.username_masked,
            "details": e.details,
            "amount": e.amount,
            "time_ago": _time_ago(e.created_at),
        })

    _recent_events_cache = cache
    _cache_updated_at = datetime.utcnow().timestamp()


def _time_ago(dt: datetime) -> str:
    """Человекочитаемое время."""
    diff = datetime.utcnow() - dt
    minutes = int(diff.total_seconds() / 60)

    if minutes < 1:
        return "только что"
    if minutes < 60:
        return f"{minutes} мин. назад"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} ч. назад"

    days = hours // 24
    return f"{days} дн. назад"


@router.callback_query(F.data == "social_proof")
async def show_social_proof(callback: CallbackQuery):
    """Показать социальное доказательство."""
    # Обновляем кэш если устарел
    import time
    if time.time() - _cache_updated_at > 1800:
        await generate_social_proof()

    async with async_session() as session:
        stats_result = await session.execute(
            select(GlobalStats).limit(1)
        )
        stats = stats_result.scalar_one_or_none()

    total_saved = stats.total_saved if stats else 0
    total_users = stats.total_users if stats else 0

    text = "📢 <b>ПРЯМО СЕЙЧАС</b>\n\n"

    if _recent_events_cache:
        for event in _recent_events_cache[:8]:
            text += (
                f"→ {event['emoji']} {event['username']} "
                f"{event['details']}\n"
                f"   <i>{event['time_ago']}</i>\n\n"
            )
    else:
        # Генерируем примеры если нет реальных данных
        examples = [
            "💰 @anna*** сэкономила 2 300₽, отключив Storytel",
            "🔍 @max*** нашёл 5 забытых подписок на 8 400₽/мес",
            "✂️ @kate*** перешла на семейный Spotify",
            "💰 @dima*** отменил Adobe CC и экономит 1 500₽/мес",
            "🔍 @lena*** обнаружила 3 подписки, о которых забыла",
        ]
        for ex in random.sample(examples, min(3, len(examples))):
            text += f"→ {ex}\n\n"

    text += (
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"💰 Всего сэкономлено:\n"
        f"<b>{format_money(total_saved)}</b>\n\n"
        f"🚀 Присоединяйся к экономии!"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="➕ Добавить подписки",
            callback_data="add_subscription",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🏆 Рейтинг",
            callback_data="leaderboard",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Главное меню",
            callback_data="back_to_menu",
        )
    )

    await callback.message.edit_text(
        text, reply_markup=builder.as_markup()
    )
    await callback.answer()