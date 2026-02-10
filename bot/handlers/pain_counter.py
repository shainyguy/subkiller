"""💀 Счётчик боли — сколько денег утекает в реальном времени."""

import logging
from datetime import date, datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select

from bot.database import (
    async_session, User, Subscription,
    SubscriptionStatus, UsageLevel,
)
from bot.utils.helpers import (
    format_money, get_monthly_price,
    get_comparable_purchase, calculate_lifetime_loss,
)
from bot.keyboards.inline import back_to_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


async def calculate_pain_data(user_id: int) -> dict:
    """Рассчитать данные для счётчика боли."""
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE.value,
                    SubscriptionStatus.TRIAL.value,
                ]),
            )
        )
        subs = list(result.scalars().all())

    if not subs:
        return {
            "total_monthly": 0,
            "wasted_monthly": 0,
            "total_daily": 0,
            "wasted_daily": 0,
            "per_minute": 0,
            "today_wasted": 0,
            "month_wasted": 0,
            "year_wasted": 0,
            "lifetime_wasted": 0,
            "comparable": "",
            "active_count": 0,
            "wasted_count": 0,
            "wasted_subs": [],
        }

    total_monthly = 0
    wasted_monthly = 0
    wasted_subs = []

    for s in subs:
        monthly = get_monthly_price(s.price, s.billing_cycle)
        total_monthly += monthly

        if s.usage_level in (
            UsageLevel.LOW.value,
            UsageLevel.NONE.value,
        ):
            wasted_monthly += monthly
            wasted_subs.append({
                "name": s.name,
                "monthly": monthly,
                "usage": s.usage_level,
            })
        elif s.usage_level == UsageLevel.UNKNOWN.value:
            # Если не оценено — считаем 50% потерей
            wasted_monthly += monthly * 0.5

    total_daily = total_monthly / 30
    wasted_daily = wasted_monthly / 30
    per_minute = wasted_daily / (24 * 60)

    # Сколько утекло сегодня (с начала дня)
    now = datetime.now()
    minutes_today = now.hour * 60 + now.minute
    today_wasted = per_minute * minutes_today

    # За месяц (с начала месяца)
    day_of_month = now.day
    month_wasted = wasted_daily * day_of_month

    # С начала года
    day_of_year = (now.date() - date(now.year, 1, 1)).days + 1
    year_wasted = wasted_daily * day_of_year

    # За жизнь (40 лет)
    lifetime_wasted = calculate_lifetime_loss(wasted_monthly)

    comparable = get_comparable_purchase(lifetime_wasted)

    active_count = len(subs)
    wasted_count = len(wasted_subs)

    return {
        "total_monthly": total_monthly,
        "wasted_monthly": wasted_monthly,
        "total_daily": total_daily,
        "wasted_daily": wasted_daily,
        "per_minute": per_minute,
        "today_wasted": today_wasted,
        "month_wasted": month_wasted,
        "year_wasted": year_wasted,
        "lifetime_wasted": lifetime_wasted,
        "comparable": comparable,
        "active_count": active_count,
        "wasted_count": wasted_count,
        "wasted_subs": wasted_subs,
    }


@router.callback_query(F.data == "pain_counter")
@router.message(Command("pain"))
@router.message(F.text == "💀 Счётчик боли")
async def show_pain_counter(event: Message | CallbackQuery):
    """Показать счётчик боли."""
    tg_id = event.from_user.id

    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == tg_id)
        )
        user = user_result.scalar_one_or_none()

    if not user:
        text = "❌ Сначала используй /start"
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return

    data = await calculate_pain_data(user.id)

    if data["total_monthly"] == 0:
        text = (
            "💀 <b>Счётчик боли</b>\n\n"
            "У тебя пока нет подписок.\n"
            "Добавь их, чтобы увидеть, сколько денег утекает!"
        )
        kb = back_to_menu_keyboard()
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=kb)
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb)
        return

    # Основной текст
    text = (
        f"💀 <b>СЧЁТЧИК ПОТЕРЬ</b>\n\n"
        f"⏱ Пока ты читаешь это сообщение,\n"
        f"у тебя утекло: <b>{data['per_minute'] * 2:.2f}₽</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
    )

    if data["wasted_monthly"] > 0:
        text += (
            f"🔴 <b>Сегодня утекло:</b> "
            f"{format_money(data['today_wasted'])}\n"
            f"🔴 <b>В этом месяце:</b> "
            f"{format_money(data['month_wasted'])}\n"
            f"🔴 <b>С начала года:</b> "
            f"{format_money(data['year_wasted'])}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📊 <b>Всего подписок:</b> {data['active_count']}\n"
            f"💰 <b>Общий бюджет:</b> "
            f"{format_money(data['total_monthly'])}/мес\n"
            f"🔥 <b>Впустую:</b> "
            f"{format_money(data['wasted_monthly'])}/мес\n\n"
        )
    else:
        text += (
            f"📊 <b>Всего подписок:</b> {data['active_count']}\n"
            f"💰 <b>Общий бюджет:</b> "
            f"{format_money(data['total_monthly'])}/мес\n\n"
            f"💡 Оцени использование подписок, "
            f"чтобы увидеть точные потери.\n\n"
        )

    if data["lifetime_wasted"] > 0:
        text += (
            f"🔴 <b>За всю жизнь ты потеряешь:</b>\n"
            f"<b>{format_money(data['lifetime_wasted'])}</b>\n"
            f"Это = {data['comparable']}\n\n"
        )

    # Топ расточительных подписок
    if data["wasted_subs"]:
        text += "⚠️ <b>Главные утечки:</b>\n"
        sorted_wasted = sorted(
            data["wasted_subs"],
            key=lambda x: x["monthly"],
            reverse=True,
        )
        for ws in sorted_wasted[:5]:
            usage_emoji = (
                "⚫" if ws["usage"] == "none" else "🔴"
            )
            text += (
                f"{usage_emoji} {ws['name']} — "
                f"{format_money(ws['monthly'])}/мес\n"
            )

        text += "\n💡 <b>Отключи их и начни экономить!</b>"

    # Кнопки действий
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()

    if data["wasted_subs"]:
        builder.row(
            InlineKeyboardButton(
                text="❌ Отключить ненужные",
                callback_data="my_subscriptions",
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🎰 А если бы инвестировал?",
                callback_data="investments",
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="📊 Полный отчёт",
            callback_data="health_dashboard",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Главное меню",
            callback_data="back_to_menu",
        )
    )

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(
            text, reply_markup=builder.as_markup()
        )
        await event.answer()
    else:

        await event.answer(text, reply_markup=builder.as_markup())
