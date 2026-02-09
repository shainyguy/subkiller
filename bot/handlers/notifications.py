"""Хендлеры уведомлений — ручное управление."""

import logging
from datetime import datetime, timedelta, date

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from sqlalchemy import select

from bot.database import (
    async_session, User, Subscription, Notification,
    NotificationType, SubscriptionStatus,
)
from bot.utils.helpers import format_money, days_until
from bot.keyboards.inline import back_to_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("reminders"))
async def show_reminders(message: Message):
    """Показать все активные напоминания."""
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(
                User.telegram_id == message.from_user.id
            )
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await message.answer("❌ Сначала /start")
            return

        notif_result = await session.execute(
            select(Notification)
            .where(
                Notification.user_id == user.id,
                Notification.sent == False,
            )
            .order_by(Notification.scheduled_at)
            .limit(20)
        )
        notifications = list(notif_result.scalars().all())

    if not notifications:
        await message.answer(
            "🔔 <b>Напоминания</b>\n\n"
            "У тебя нет активных напоминаний.\n"
            "Добавь подписки, и я буду напоминать "
            "о списаниях!",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    text = f"🔔 <b>Активные напоминания</b> ({len(notifications)}):\n\n"

    type_emoji = {
        NotificationType.RENEWAL_REMINDER.value: "⏰",
        NotificationType.TRIAL_ENDING.value: "🆓",
        NotificationType.WEEKLY_REPORT.value: "📊",
        NotificationType.UNUSED_ALERT.value: "⚠️",
        NotificationType.PREDICTION.value: "🔮",
        NotificationType.ACHIEVEMENT.value: "🏅",
    }

    for n in notifications:
        emoji = type_emoji.get(
            n.notification_type, "🔔"
        )
        d = days_until(n.scheduled_at.date())
        time_str = n.scheduled_at.strftime("%d.%m %H:%M")
        text += (
            f"{emoji} {n.message or 'Уведомление'}\n"
            f"   📅 {time_str} (через {max(0, d)} дн.)\n\n"
        )

    await message.answer(
        text, reply_markup=back_to_menu_keyboard()
    )


@router.callback_query(F.data == "upcoming_payments")
async def show_upcoming_payments(callback: CallbackQuery):
    """Показать ближайшие списания."""
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(
                User.telegram_id == callback.from_user.id
            )
        )
        user = user_result.scalar_one_or_none()

        if not user:
            await callback.answer("❌ /start", show_alert=True)
            return

        subs_result = await session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status.in_([
                    SubscriptionStatus.ACTIVE.value,
                    SubscriptionStatus.TRIAL.value,
                ]),
                Subscription.next_billing_date.isnot(None),
            )
            .order_by(Subscription.next_billing_date)
            .limit(15)
        )
        subs = list(subs_result.scalars().all())

    if not subs:
        await callback.message.edit_text(
            "📅 Нет ближайших списаний.",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
        return

    text = "📅 <b>Ближайшие списания</b>\n\n"
    total_upcoming = 0

    for s in subs:
        d = days_until(s.next_billing_date)
        date_str = s.next_billing_date.strftime("%d.%m")

        if d <= 0:
            emoji = "🔴"
        elif d <= 3:
            emoji = "🟠"
        elif d <= 7:
            emoji = "🟡"
        else:
            emoji = "🟢"

        trial_mark = " 🆓" if s.is_trial else ""
        text += (
            f"{emoji} <b>{s.name}</b>{trial_mark}\n"
            f"   {format_money(s.price)} — {date_str} "
            f"(через {d} дн.)\n\n"
        )
        total_upcoming += s.price

    text += (
        f"💰 Итого ближайших списаний: "
        f"<b>{format_money(total_upcoming)}</b>"
    )

    await callback.message.edit_text(
        text, reply_markup=back_to_menu_keyboard()
    )
    await callback.answer()