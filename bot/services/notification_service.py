"""Сервис уведомлений — проверка и отправка."""

import logging
from datetime import datetime

from aiogram import Bot
from sqlalchemy import select

from bot.database import (
    async_session, Notification, User,
    Subscription, SubscriptionStatus,
)
from bot.utils.helpers import format_money, get_monthly_price
from bot.keyboards.inline import back_to_menu_keyboard

logger = logging.getLogger(__name__)


async def check_and_send_notifications(bot: Bot):
    """
    Проверка и отправка запланированных уведомлений.
    Вызывается планировщиком каждый час.
    """
    now = datetime.utcnow()

    async with async_session() as session:
        # Находим неотправленные уведомления,
        # время которых наступило
        result = await session.execute(
            select(Notification)
            .where(
                Notification.sent == False,
                Notification.scheduled_at <= now,
            )
            .limit(100)
        )
        notifications = list(result.scalars().all())

        if not notifications:
            return

        logger.info(
            f"Отправка {len(notifications)} уведомлений..."
        )

        for notif in notifications:
            try:
                # Получаем пользователя
                user_result = await session.execute(
                    select(User).where(User.id == notif.user_id)
                )
                user = user_result.scalar_one_or_none()

                if not user or not user.notifications_enabled:
                    notif.sent = True
                    notif.sent_at = now
                    continue

                # Формируем сообщение
                message_text = notif.message or ""

                # Дополнительная информация для trial
                if (
                    notif.notification_type == "trial_ending"
                    and notif.subscription_id
                ):
                    sub_result = await session.execute(
                        select(Subscription).where(
                            Subscription.id == notif.subscription_id
                        )
                    )
                    sub = sub_result.scalar_one_or_none()

                    if sub and sub.status == SubscriptionStatus.TRIAL.value:
                        from aiogram.types import InlineKeyboardButton
                        from aiogram.utils.keyboard import (
                            InlineKeyboardBuilder,
                        )

                        builder = InlineKeyboardBuilder()
                        builder.row(
                            InlineKeyboardButton(
                                text="✅ Продлить",
                                callback_data=f"view_sub_{sub.id}",
                            ),
                            InlineKeyboardButton(
                                text="❌ Отменить",
                                callback_data=f"cancel_sub_{sub.id}",
                            ),
                        )

                        message_text = (
                            f"🆓⚠️ <b>Trial {sub.name} "
                            f"заканчивается завтра!</b>\n\n"
                            f"После окончания с тебя начнут "
                            f"списывать {format_money(sub.price)} "
                            f"каждый месяц.\n\n"
                            f"Что делаем?"
                        )

                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=message_text,
                            reply_markup=builder.as_markup(),
                        )
                        notif.sent = True
                        notif.sent_at = now
                        continue

                # Для обычных напоминаний
                if notif.notification_type == "renewal_reminder":
                    if notif.subscription_id:
                        sub_result = await session.execute(
                            select(Subscription).where(
                                Subscription.id == notif.subscription_id
                            )
                        )
                        sub = sub_result.scalar_one_or_none()

                        if sub and sub.status == SubscriptionStatus.CANCELLED.value:
                            # Подписка уже отменена
                            notif.sent = True
                            notif.sent_at = now
                            continue

                        if sub:
                            from aiogram.types import InlineKeyboardButton
                            from aiogram.utils.keyboard import (
                                InlineKeyboardBuilder,
                            )

                            builder = InlineKeyboardBuilder()
                            builder.row(
                                InlineKeyboardButton(
                                    text="📋 Посмотреть",
                                    callback_data=f"view_sub_{sub.id}",
                                ),
                                InlineKeyboardButton(
                                    text="❌ Отменить",
                                    callback_data=f"cancel_sub_{sub.id}",
                                ),
                            )

                            await bot.send_message(
                                chat_id=user.telegram_id,
                                text=f"🔔 {message_text}",
                                reply_markup=builder.as_markup(),
                            )
                            notif.sent = True
                            notif.sent_at = now
                            continue

                # Обычное уведомление
                if message_text:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"🔔 {message_text}",
                        reply_markup=back_to_menu_keyboard(),
                    )

                notif.sent = True
                notif.sent_at = now

            except Exception as e:
                logger.error(
                    f"Ошибка отправки уведомления "
                    f"{notif.id}: {e}"
                )
                # Не помечаем как отправленное,
                # попробуем в следующий раз
                continue

        await session.commit()
        logger.info("Уведомления обработаны.")