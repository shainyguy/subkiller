"""🏆 Лидерборд экономии + система ачивок."""

import logging
from datetime import date, datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select, func, desc

from bot.database import (
    async_session, User, Subscription,
    UserAchievement, SubscriptionStatus, UsageLevel,
)
from bot.utils.helpers import format_money, get_monthly_price
from bot.keyboards.inline import back_to_menu_keyboard
from bot.config import ACHIEVEMENTS

logger = logging.getLogger(__name__)
router = Router()


# ============== Проверка ачивок ==============

async def check_achievements(telegram_id: int) -> list[dict]:
    """
    Проверить и выдать новые ачивки.
    Возвращает список новых ачивок.
    """
    new_achievements = []

    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            return []

        # Получаем существующие ачивки
        existing_result = await session.execute(
            select(UserAchievement.achievement_key).where(
                UserAchievement.user_id == user.id
            )
        )
        existing_keys = set(
            row[0] for row in existing_result.fetchall()
        )

        # Подписки
        subs_result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id
            )
        )
        all_subs = list(subs_result.scalars().all())

        active_subs = [
            s for s in all_subs
            if s.status in (
                SubscriptionStatus.ACTIVE.value,
                SubscriptionStatus.TRIAL.value,
            )
        ]
        cancelled_subs = [
            s for s in all_subs
            if s.status == SubscriptionStatus.CANCELLED.value
        ]

        # Месячная экономия
        saved_monthly = user.total_saved

        checks = []

        # --- Подписки ---
        if all_subs and "first_sub_added" not in existing_keys:
            checks.append("first_sub_added")

        # --- Отмены ---
        if (
            cancelled_subs
            and "first_sub_cancelled" not in existing_keys
        ):
            checks.append("first_sub_cancelled")

        if (
            len(cancelled_subs) >= 5
            and "five_subs_cancelled" not in existing_keys
        ):
            checks.append("five_subs_cancelled")

        if (
            len(cancelled_subs) >= 10
            and "ten_subs_cancelled" not in existing_keys
        ):
            checks.append("ten_subs_cancelled")

        # --- Экономия ---
        if (
            saved_monthly >= 1000
            and "saved_1000" not in existing_keys
        ):
            checks.append("saved_1000")

        if (
            saved_monthly >= 5000
            and "saved_5000" not in existing_keys
        ):
            checks.append("saved_5000")

        if (
            saved_monthly >= 10000
            and "saved_10000" not in existing_keys
        ):
            checks.append("saved_10000")

        if (
            saved_monthly >= 50000
            and "saved_50000" not in existing_keys
        ):
            checks.append("saved_50000")

        if (
            saved_monthly >= 100000
            and "saved_100000" not in existing_keys
        ):
            checks.append("saved_100000")

        # --- Стрики ---
        if (
            user.current_streak >= 7
            and "week_streak" not in existing_keys
        ):
            checks.append("week_streak")

        if (
            user.current_streak >= 30
            and "month_streak" not in existing_keys
        ):
            checks.append("month_streak")

        # --- Без новых подписок ---
        if user.last_new_sub_date:
            days_no_new = (
                date.today() - user.last_new_sub_date
            ).days
            if (
                days_no_new >= 7
                and "no_new_subs_week" not in existing_keys
            ):
                checks.append("no_new_subs_week")
            if (
                days_no_new >= 30
                and "no_new_subs_month" not in existing_keys
            ):
                checks.append("no_new_subs_month")

        # --- Здоровье ---
        from bot.utils.helpers import get_health_score
        if active_subs:
            used = sum(
                1 for s in active_subs
                if s.usage_level in (
                    UsageLevel.HIGH.value,
                    UsageLevel.MEDIUM.value,
                )
            )
            total_m = sum(
                get_monthly_price(s.price, s.billing_cycle)
                for s in active_subs
            )
            wasted_m = sum(
                get_monthly_price(s.price, s.billing_cycle)
                for s in active_subs
                if s.usage_level in (
                    UsageLevel.LOW.value,
                    UsageLevel.NONE.value,
                )
            )
            score = get_health_score(
                len(active_subs), used, total_m, wasted_m
            )

            if (
                score >= 80
                and "health_score_80" not in existing_keys
            ):
                checks.append("health_score_80")
            if (
                score >= 100
                and "health_score_100" not in existing_keys
            ):
                checks.append("health_score_100")

        # --- Рефералы ---
        referral_count_result = await session.execute(
            select(func.count(User.id)).where(
                User.referred_by == telegram_id
            )
        )
        referral_count = referral_count_result.scalar() or 0

        if (
            referral_count >= 1
            and "invited_friend" not in existing_keys
        ):
            checks.append("invited_friend")

        if (
            referral_count >= 5
            and "invited_five" not in existing_keys
        ):
            checks.append("invited_five")

        # Сохраняем новые ачивки
        for key in checks:
            if key in ACHIEVEMENTS:
                ach = UserAchievement(
                    user_id=user.id,
                    achievement_key=key,
                )
                session.add(ach)
                new_achievements.append(ACHIEVEMENTS[key])

        if new_achievements:
            await session.commit()

    return new_achievements


# ============== Лидерборд ==============

@router.callback_query(F.data == "leaderboard")
@router.message(Command("top"))
@router.message(F.text == "🏆 Рейтинг")
async def show_leaderboard(event: Message | CallbackQuery):
    """Показать рейтинг экономии."""
    tg_id = event.from_user.id

    async with async_session() as session:
        # Топ-10 по экономии
        top_result = await session.execute(
            select(User)
            .where(User.total_saved > 0)
            .order_by(desc(User.total_saved))
            .limit(10)
        )
        top_users = list(top_result.scalars().all())

        # Позиция текущего пользователя
        user_result = await session.execute(
            select(User).where(User.telegram_id == tg_id)
        )
        current_user = user_result.scalar_one_or_none()

        # Общее количество
        total_result = await session.execute(
            select(func.count(User.id)).where(
                User.total_saved > 0
            )
        )
        total_savers = total_result.scalar() or 0

        # Позиция пользователя
        user_position = 0
        if current_user and current_user.total_saved > 0:
            pos_result = await session.execute(
                select(func.count(User.id)).where(
                    User.total_saved > current_user.total_saved
                )
            )
            user_position = (pos_result.scalar() or 0) + 1

    medals = ["🥇", "🥈", "🥉"]
    text = "🏆 <b>РЕЙТИНГ ЭКОНОМИИ</b>\n\n"

    if not top_users:
        text += (
            "Пока никто не сэкономил.\n"
            "Стань первым — отмени ненужные подписки! 💪"
        )
    else:
        for i, u in enumerate(top_users):
            medal = medals[i] if i < 3 else f"{i + 1}."

            name = u.username or u.first_name or "Аноним"
            if u.telegram_id == tg_id:
                name = f"<b>→ {name} (ты)</b>"
            else:
                # Маскируем имя
                if len(name) > 3:
                    name = name[:3] + "***"

            text += (
                f"{medal} @{name} — "
                f"сэкономил {format_money(u.total_saved)}/мес\n"
            )

        text += "\n"

        if current_user and user_position > 10:
            text += (
                f"...\n"
                f"{user_position}. <b>Ты</b> — "
                f"{format_money(current_user.total_saved)}/мес\n\n"
            )

        if current_user:
            text += (
                f"📊 Всего участников: {total_savers}\n"
                f"📍 Твоя позиция: #{user_position}\n\n"
            )

            if user_position > 10:
                # Рассчитываем, сколько нужно сэкономить
                if top_users:
                    tenth_saved = top_users[-1].total_saved
                    need_more = tenth_saved - (
                        current_user.total_saved or 0
                    )
                    if need_more > 0:
                        text += (
                            f"💪 Отключи ещё подписок на "
                            f"{format_money(need_more)}/мес "
                            f"и войди в TOP-10!\n\n"
                        )

        text += "🎁 <b>TOP-10 получают Premium бесплатно!</b>"

    # Ачивки текущего пользователя
    if current_user:
        async with async_session() as session:
            ach_result = await session.execute(
                select(UserAchievement).where(
                    UserAchievement.user_id == current_user.id
                )
            )
            user_achs = list(ach_result.scalars().all())

        if user_achs:
            text += "\n\n🏅 <b>Твои ачивки:</b>\n"
            for ua in user_achs:
                ach_data = ACHIEVEMENTS.get(ua.achievement_key)
                if ach_data:
                    text += (
                        f"{ach_data['emoji']} {ach_data['name']} "
                        f"— {ach_data['description']}\n"
                    )

        # Показываем незаработанные
        locked = set(ACHIEVEMENTS.keys()) - set(
            ua.achievement_key for ua in user_achs
        )
        if locked:
            text += "\n🔒 <b>Ещё можно получить:</b>\n"
            count = 0
            for key in locked:
                if count >= 3:
                    remaining = len(locked) - 3
                    text += f"   ...и ещё {remaining}\n"
                    break
                ach = ACHIEVEMENTS[key]
                text += f"   🔒 {ach['name']}\n"
                count += 1

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📋 Мои подписки",
            callback_data="my_subscriptions",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="👥 Пригласить друга",
            callback_data="referral",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Главное меню",
            callback_data="back_to_menu",
        )
    )

    # Проверяем новые ачивки
    if current_user:
        new_achs = await check_achievements(tg_id)
        if new_achs:
            ach_text = "\n\n🎉 <b>НОВЫЕ АЧИВКИ!</b>\n"
            for a in new_achs:
                ach_text += f"{a['emoji']} {a['name']} — {a['description']}\n"
            text += ach_text

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(
            text, reply_markup=builder.as_markup()
        )
        await event.answer()
    else:
        await event.answer(text, reply_markup=builder.as_markup())