"""Вспомогательные функции."""

import hashlib
import random
import string
from datetime import date, datetime, timedelta
from typing import Optional
from bot.database.models import BillingCycle


def generate_referral_code(telegram_id: int) -> str:
    """Генерация уникального реферального кода."""
    hash_part = hashlib.md5(
        str(telegram_id).encode()
    ).hexdigest()[:6]
    return f"sk_{hash_part}"


def mask_username(username: Optional[str]) -> str:
    """Маскировка имени пользователя для social proof."""
    if not username:
        letters = random.choices(string.ascii_lowercase, k=4)
        return f"@{''.join(letters)}***"
    if len(username) <= 3:
        return f"@{username}***"
    return f"@{username[:4]}***"


def format_money(amount: float, currency: str = "RUB") -> str:
    """Форматирование суммы денег."""
    if currency == "RUB":
        if amount >= 1_000_000:
            return f"{amount / 1_000_000:.1f} млн ₽"
        if amount >= 1000:
            return f"{amount:,.0f}₽".replace(",", " ")
        return f"{amount:.0f}₽"
    return f"${amount:,.2f}"


def get_monthly_price(
    price: float, billing_cycle: str
) -> float:
    """Приведение цены к месячному значению."""
    multipliers = {
        BillingCycle.WEEKLY.value: price * 4.33,
        BillingCycle.MONTHLY.value: price,
        BillingCycle.QUARTERLY.value: price / 3,
        BillingCycle.SEMI_ANNUAL.value: price / 6,
        BillingCycle.ANNUAL.value: price / 12,
    }
    return multipliers.get(billing_cycle, price)


def get_next_billing_date(
    current_date: date, billing_cycle: str
) -> date:
    """Расчёт следующей даты списания."""
    deltas = {
        BillingCycle.WEEKLY.value: timedelta(weeks=1),
        BillingCycle.MONTHLY.value: timedelta(days=30),
        BillingCycle.QUARTERLY.value: timedelta(days=90),
        BillingCycle.SEMI_ANNUAL.value: timedelta(days=180),
        BillingCycle.ANNUAL.value: timedelta(days=365),
    }
    delta = deltas.get(billing_cycle, timedelta(days=30))
    return current_date + delta


def days_until(target_date: date) -> int:
    """Дней до указанной даты."""
    return (target_date - date.today()).days


def calculate_yearly_cost(
    price: float, billing_cycle: str
) -> float:
    """Расчёт годовой стоимости подписки."""
    monthly = get_monthly_price(price, billing_cycle)
    return monthly * 12


def calculate_investment_return(
    monthly_amount: float,
    years: int,
    annual_return: float = 0.10,
) -> float:
    """Расчёт инвестиционного дохода с ежемесячным взносом."""
    monthly_rate = annual_return / 12
    months = years * 12
    if monthly_rate == 0:
        return monthly_amount * months
    # Формула будущей стоимости аннуитета
    fv = monthly_amount * (
        ((1 + monthly_rate) ** months - 1) / monthly_rate
    )
    return round(fv, 0)


def calculate_lifetime_loss(
    monthly_waste: float, years: int = 40
) -> float:
    """Расчёт потери денег за всю жизнь."""
    return monthly_waste * 12 * years


def get_comparable_purchase(amount: float) -> str:
    """Находит понятное сравнение для суммы."""
    comparisons = [
        (500, "🍕 2 пиццы"),
        (1000, "🎬 5 билетов в кино"),
        (3000, "🎧 AirPods"),
        (5000, "📱 чехол для iPhone"),
        (10000, "🎮 игровая подписка на год"),
        (20000, "✈️ перелёт в Турцию"),
        (50000, "📺 хороший телевизор"),
        (100000, "💻 MacBook Air"),
        (200000, "🏍 скутер"),
        (500000, "🚗 подержанная машина"),
        (1000000, "🏠 первый взнос на квартиру"),
        (2000000, "🚗 Toyota Camry"),
        (5000000, "🏠 квартира в регионе"),
        (10000000, "🏠 квартира в Москве"),
    ]
    for threshold, item in reversed(comparisons):
        if amount >= threshold:
            return item
    return "☕ пару чашек кофе"


def get_health_score(
    active_subs: int,
    used_subs: int,
    total_monthly: float,
    wasted_monthly: float,
) -> int:
    """Рассчитать оценку подписочного здоровья (0-100)."""
    if active_subs == 0:
        return 100

    # Доля используемых подписок (40%)
    usage_ratio = used_subs / active_subs if active_subs > 0 else 1
    usage_score = usage_ratio * 40

    # Доля полезных трат (40%)
    if total_monthly > 0:
        efficiency = 1 - (wasted_monthly / total_monthly)
    else:
        efficiency = 1
    efficiency_score = max(0, efficiency) * 40

    # Количество подписок (20%)
    # Штраф за слишком много подписок
    if active_subs <= 3:
        count_score = 20
    elif active_subs <= 6:
        count_score = 15
    elif active_subs <= 10:
        count_score = 10
    else:
        count_score = 5

    total = usage_score + efficiency_score + count_score
    return max(0, min(100, int(total)))


def health_emoji(score: int) -> str:
    """Эмодзи для оценки здоровья."""
    if score >= 80:
        return "💚"
    if score >= 60:
        return "💛"
    if score >= 40:
        return "🧡"
    return "🤒"


def billing_cycle_name(cycle: str) -> str:
    """Русское название периода."""
    names = {
        BillingCycle.WEEKLY.value: "еженедельно",
        BillingCycle.MONTHLY.value: "ежемесячно",
        BillingCycle.QUARTERLY.value: "раз в 3 месяца",
        BillingCycle.SEMI_ANNUAL.value: "раз в полгода",
        BillingCycle.ANNUAL.value: "ежегодно",
    }
    return names.get(cycle, "ежемесячно")