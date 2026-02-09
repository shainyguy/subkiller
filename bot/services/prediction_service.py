"""Сервис предсказаний — локальные алгоритмы без AI."""

import logging
from datetime import date, datetime

from bot.database.models import Subscription, UsageLevel

logger = logging.getLogger(__name__)


def predict_abandonment(sub: Subscription) -> dict:
    """
    Локальное предсказание заброса подписки
    (фоллбэк без GigaChat).
    """
    days_since_signup = (
        datetime.utcnow() - sub.created_at
    ).days

    days_since_last_use = 0
    if sub.last_used:
        days_since_last_use = (
            date.today() - sub.last_used
        ).days
    elif sub.usage_level in (
        UsageLevel.LOW.value,
        UsageLevel.NONE.value,
    ):
        days_since_last_use = max(30, days_since_signup)

    # Базовая вероятность
    base_prob = 0

    # Фактор неиспользования
    if sub.usage_level == UsageLevel.NONE.value:
        base_prob += 70
    elif sub.usage_level == UsageLevel.LOW.value:
        base_prob += 50
    elif sub.usage_level == UsageLevel.MEDIUM.value:
        base_prob += 20
    elif sub.usage_level == UsageLevel.HIGH.value:
        base_prob += 5
    else:
        base_prob += 40  # unknown

    # Фактор времени без использования
    if days_since_last_use > 60:
        base_prob += 20
    elif days_since_last_use > 30:
        base_prob += 10
    elif days_since_last_use > 14:
        base_prob += 5

    # Trial-фактор
    if sub.is_trial:
        base_prob += 15

    probability = min(95, max(5, base_prob))

    from bot.utils.helpers import get_monthly_price
    monthly = get_monthly_price(sub.price, sub.billing_cycle)

    return {
        "will_abandon": probability >= 60,
        "probability_percent": probability,
        "predicted_waste_6months": monthly * 6 * (probability / 100),
        "recommendation": _get_recommendation(probability, sub),
        "reason": _get_reason(
            days_since_last_use, sub.usage_level
        ),
    }


def _get_recommendation(prob: int, sub: Subscription) -> str:
    if prob >= 80:
        return f"Срочно отмени {sub.name} — деньги улетают впустую"
    if prob >= 60:
        return f"Попробуй заменить {sub.name} на бесплатную альтернативу"
    if prob >= 40:
        return f"Оцени, нужен ли тебе {sub.name} на следующий месяц"
    return f"{sub.name} используется нормально"


def _get_reason(days_since_last_use: int, usage: str) -> str:
    if usage == UsageLevel.NONE.value:
        return "Ты не используешь эту подписку совсем"
    if days_since_last_use > 60:
        return f"Не использовалась уже {days_since_last_use} дней"
    if days_since_last_use > 30:
        return f"Последнее использование {days_since_last_use} дней назад"
    if usage == UsageLevel.LOW.value:
        return "Используется очень редко"
    return "Используется нерегулярно"