"""Аналитический сервис — расчёты для дашбордов."""

import logging
from datetime import date, datetime
from typing import Optional

from sqlalchemy import select, func

from bot.database import (
    async_session, User, Subscription,
    SubscriptionStatus, UsageLevel,
)
from bot.utils.helpers import get_monthly_price

logger = logging.getLogger(__name__)


async def get_user_analytics(user_id: int) -> dict:
    """Полная аналитика по пользователю."""
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user_id
            )
        )
        all_subs = list(result.scalars().all())

    active = [
        s for s in all_subs
        if s.status in (
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIAL.value,
        )
    ]
    cancelled = [
        s for s in all_subs
        if s.status == SubscriptionStatus.CANCELLED.value
    ]

    total_monthly = sum(
        get_monthly_price(s.price, s.billing_cycle)
        for s in active
    )

    wasted_monthly = sum(
        get_monthly_price(s.price, s.billing_cycle)
        for s in active
        if s.usage_level in (
            UsageLevel.LOW.value,
            UsageLevel.NONE.value,
        )
    )

    saved_monthly = sum(
        get_monthly_price(s.price, s.billing_cycle)
        for s in cancelled
    )

    # Категории
    categories = {}
    for s in active:
        m = get_monthly_price(s.price, s.billing_cycle)
        cat = s.category or "other"
        categories[cat] = categories.get(cat, 0) + m

    # Самая дорогая
    most_expensive = None
    if active:
        most_expensive = max(
            active,
            key=lambda s: get_monthly_price(
                s.price, s.billing_cycle
            ),
        )

    # Самая бесполезная
    most_wasted = None
    wasted_subs = [
        s for s in active
        if s.usage_level in (
            UsageLevel.LOW.value,
            UsageLevel.NONE.value,
        )
    ]
    if wasted_subs:
        most_wasted = max(
            wasted_subs,
            key=lambda s: get_monthly_price(
                s.price, s.billing_cycle
            ),
        )

    return {
        "total_subs": len(all_subs),
        "active_count": len(active),
        "cancelled_count": len(cancelled),
        "total_monthly": total_monthly,
        "total_yearly": total_monthly * 12,
        "wasted_monthly": wasted_monthly,
        "wasted_yearly": wasted_monthly * 12,
        "saved_monthly": saved_monthly,
        "saved_yearly": saved_monthly * 12,
        "categories": categories,
        "most_expensive": most_expensive,
        "most_wasted": most_wasted,
    }