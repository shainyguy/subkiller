"""📊 Еженедельный отчёт — отправка каждый понедельник."""

import logging
from datetime import date, datetime

from aiogram import Bot, Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select

from bot.database import (
    async_session, User, Subscription,
    SubscriptionStatus, UsageLevel,
)
from bot.utils.helpers import (
    format_money, get_monthly_price,
    get_health_score, health_emoji,
)
from bot.keyboards.inline import back_to_menu_keyboard
from bot.config import ALTERNATIVES_DB

logger = logging.getLogger(__name__)
router = Router()


async def generate_weekly_report(user: User) -> str:
    """Генерация текста еженедельного отчёта."""
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE.value,
                    SubscriptionStatus.TRIAL.value,
                ]),
            )
        )
        subs = list(result.scalars().all())

    if not subs:
        return ""

    green = []
    yellow = []
    red = []
    total_monthly = 0
    wasted_monthly = 0

    for s in subs:
        monthly = get_monthly_price(s.price, s.billing_cycle)
        total_monthly += monthly

        if s.usage_level == UsageLevel.HIGH.value:
            green.append(s)
        elif s.usage_level == UsageLevel.MEDIUM.value:
            yellow.append(s)
        elif s.usage_level in (
            UsageLevel.LOW.value,
            UsageLevel.NONE.value,
        ):
            red.append(s)
            wasted_monthly += monthly
        else:
            wasted_monthly += monthly * 0.3

    used_count = len(green) + len(yellow)
    score = get_health_score(
        len(subs), used_count,
        total_monthly, wasted_monthly,
    )
    h_emoji = health_emoji(score)

    text = (
        f"📊 <b>ЕЖЕНЕДЕЛЬНЫЙ ОТЧЁТ SubKiller</b>\n"
        f"📅 {date.today().strftime('%d.%m.%Y')}\n\n"
        f"💰 Общий бюджет подписок: "
        f"<b>{format_money(total_monthly)}/мес</b>\n\n"
    )

    if green:
        g_total = sum(
            get_monthly_price(s.price, s.billing_cycle)
            for s in green
        )
        names = ", ".join(s.name for s in green)
        text += (
            f"🟢 Активно используешь ({len(green)}): "
            f"{format_money(g_total)}\n"
            f"   {names}\n\n"
        )

    if yellow:
        y_total = sum(
            get_monthly_price(s.price, s.billing_cycle)
            for s in yellow
        )
        names = ", ".join(s.name for s in yellow)
        text += (
            f"🟡 Редко используешь ({len(yellow)}): "
            f"{format_money(y_total)}\n"
            f"   {names}\n\n"
        )

    if red:
        r_total = sum(
            get_monthly_price(s.price, s.billing_cycle)
            for s in red
        )
        names = ", ".join(s.name for s in red)
        text += (
            f"🔴 Не используешь ({len(red)}): "
            f"{format_money(r_total)}\n"
            f"   {names}\n\n"
        )

    pct = (
        int(wasted_monthly / total_monthly * 100)
        if total_monthly > 0 else 0
    )
    text += (
        f"Оценка здоровья: <b>{score}/100</b> {h_emoji}\n"
    )
    if pct > 0:
        text += f"(ты переплачиваешь {pct}%)\n\n"
    else:
        text += "\n"

    # Рекомендации
    recommendations = []
    for s in red:
        m = get_monthly_price(s.price, s.billing_cycle)
        alts = ALTERNATIVES_DB.get(s.name, [])
        if alts:
            best = alts[0]
            alt_price = best.get("price", 0)
            if alt_price == 0:
                recommendations.append(
                    f"→ Заменить {s.name} ({format_money(m)}) "
                    f"→ {best['name']} (бесплатно)"
                )
            elif alt_price < m:
                recommendations.append(
                    f"→ Заменить {s.name} ({format_money(m)}) "
                    f"→ {best['name']} ({format_money(alt_price)})"
                )
        else:
            recommendations.append(
                f"→ Отменить {s.name} ({format_money(m)})"
            )

    if recommendations:
        text += "<b>Рекомендации:</b>\n"
        for r in recommendations[:5]:
            text += f"{r}\n"
        text += "\n"

    if wasted_monthly > 0:
        text += (
            f"💡 <b>Потенциальная экономия:</b>\n"
            f"{format_money(wasted_monthly)}/мес = "
            f"{format_money(wasted_monthly * 12)}/год 🎉\n"
        )

    return text


async def send_weekly_reports(bot: Bot):
    """Отправка еженедельных отчётов всем пользователям."""
    logger.info("Начинаем рассылку еженедельных отчётов...")

    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.weekly_report_enabled == True,
                User.notifications_enabled == True,
            )
        )
        users = list(result.scalars().all())

    sent = 0
    errors = 0

    for user in users:
        try:
            report = await generate_weekly_report(user)
            if not report:
                continue

            from aiogram.utils.keyboard import InlineKeyboardBuilder
            from aiogram.types import InlineKeyboardButton

            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(
                    text="📋 Управлять подписками",
                    callback_data="my_subscriptions",
                )
            )
            builder.row(
                InlineKeyboardButton(
                    text="💀 Счётчик боли",
                    callback_data="pain_counter",
                )
            )

            await bot.send_message(
                chat_id=user.telegram_id,
                text=report,
                reply_markup=builder.as_markup(),
            )
            sent += 1

        except Exception as e:
            logger.error(
                f"Report error for {user.telegram_id}: {e}"
            )
            errors += 1

    logger.info(
        f"Отчёты отправлены: {sent}, ошибок: {errors}"
    )