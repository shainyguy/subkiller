"""Парсинг пересланных SMS/email через GigaChat."""

import logging
from datetime import date, datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy import select

from bot.database import (
    async_session, User, Subscription,
    SubscriptionStatus, UsageLevel, BillingCycle,
    GlobalStats, SocialProofEvent, Notification,
    NotificationType,
)
from bot.services.gigachat_service import gigachat_service
from bot.utils.helpers import (
    format_money, get_monthly_price,
    mask_username, get_next_billing_date,
)
from bot.keyboards.inline import back_to_menu_keyboard
from bot.config import SUBSCRIPTION_CATEGORIES

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "add_from_message")
async def prompt_forward_message(callback):
    """Просьба переслать сообщение."""
    text = (
        "📩 <b>Пересылка уведомлений</b>\n\n"
        "Перешли мне:\n"
        "• SMS от банка о списании\n"
        "• Email-подтверждение подписки\n"
        "• Уведомление об оплате\n"
        "• Скриншот (опиши текстом)\n\n"
        "Я найду в тексте информацию о подписке "
        "и добавлю её автоматически 🤖\n\n"
        "Можешь переслать несколько сообщений подряд!"
    )
    await callback.message.edit_text(text)
    await callback.answer()


@router.message(
    F.forward_date | F.text,
    ~F.text.startswith("/"),
    StateFilter(None),
)
async def parse_forwarded_message(message: Message):
    """Обработка пересланных сообщений и обычного текста."""
    # Проверяем, что это не команда и не кнопка
    if not message.text:
        return

    known_buttons = [
        "📋 Подписки", "💀 Счётчик боли",
        "➕ Добавить", "📊 Отчёт",
        "🏆 Рейтинг", "⭐ Premium",
        "🌐 Mini App",
    ]
    if message.text in known_buttons:
        return

    # Проверяем, что текст похож на уведомление
    # (содержит ключевые слова)
    keywords = [
        "списан", "оплат", "подписк", "subscription",
        "payment", "charge", "renewal", "trial",
        "автоплатёж", "recurring", "пробный период",
        "продлен", "тариф", "месяц", "руб", "₽",
        "rub", "usd", "$", "спишет", "покупка",
        "apple", "google", "play", "store",
    ]

    text_lower = message.text.lower()
    has_keyword = any(kw in text_lower for kw in keywords)

    if not has_keyword and not message.forward_date:
        return  # Не похоже на уведомление о подписке

    # Проверяем пользователя
    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == message.from_user.id
            )
        )
        user = result.scalar_one_or_none()

    if not user:
        await message.answer(
            "❌ Сначала используй /start"
        )
        return

    # Отправляем в GigaChat
    processing_msg = await message.answer(
        "🔍 Анализирую сообщение..."
    )

    try:
        found_subs = (
            await gigachat_service.parse_subscription_from_text(
                message.text
            )
        )
    except Exception as e:
        logger.error(f"GigaChat error: {e}")
        await processing_msg.edit_text(
            "❌ Не удалось проанализировать сообщение. "
            "Попробуй ещё раз или добавь подписку вручную.",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    if not found_subs:
        await processing_msg.edit_text(
            "🤔 Не нашёл подписок в этом сообщении.\n\n"
            "Попробуй:\n"
            "• Переслать другое уведомление\n"
            "• Добавить подписку вручную\n"
            "• Выбрать из списка",
            reply_markup=back_to_menu_keyboard(),
        )
        return

    # Добавляем найденные подписки
    added = []
    skipped = []

    async with async_session() as session:
        for sub_data in found_subs:
            confidence = sub_data.get("confidence", 0.5)
            if confidence < 0.3:
                continue

            name = sub_data.get("name", "Неизвестный сервис")
            price = sub_data.get("price", 0)
            cycle = sub_data.get(
                "billing_cycle", BillingCycle.MONTHLY.value
            )
            category = sub_data.get("category", "other")
            is_trial = sub_data.get("is_trial", False)

            if price <= 0:
                skipped.append(name)
                continue

            # Проверяем дубликаты
            existing = await session.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.name == name,
                    Subscription.status.in_([
                        SubscriptionStatus.ACTIVE.value,
                        SubscriptionStatus.TRIAL.value,
                    ]),
                )
            )
            if existing.scalar_one_or_none():
                skipped.append(f"{name} (уже есть)")
                continue

            next_billing = get_next_billing_date(
                date.today(), cycle
            )

            sub = Subscription(
                user_id=user.id,
                name=name,
                price=price,
                category=category,
                billing_cycle=cycle,
                next_billing_date=next_billing,
                is_trial=is_trial,
                trial_end_date=next_billing if is_trial else None,
                status=(
                    SubscriptionStatus.TRIAL.value
                    if is_trial
                    else SubscriptionStatus.ACTIVE.value
                ),
                usage_level=UsageLevel.UNKNOWN.value,
            )
            session.add(sub)
            added.append(sub_data)

            # Уведомление о продлении
            reminder_date = datetime.combine(
                next_billing - timedelta(days=3),
                datetime.min.time().replace(hour=10),
            )
            if reminder_date > datetime.utcnow():
                notif = Notification(
                    user_id=user.id,
                    notification_type=NotificationType.RENEWAL_REMINDER.value,
                    message=(
                        f"⏰ Через 3 дня спишется "
                        f"{format_money(price)} за {name}!"
                    ),
                    scheduled_at=reminder_date,
                )
                session.add(notif)

        # Обновляем статистику
        if added:
            stats_result = await session.execute(
                select(GlobalStats).limit(1)
            )
            stats = stats_result.scalar_one_or_none()
            if stats:
                stats.total_subscriptions_found += len(added)

            # Social proof
            total_found_amount = sum(
                s.get("price", 0) for s in added
            )
            social_event = SocialProofEvent(
                user_id=message.from_user.id,
                username_masked=mask_username(
                    message.from_user.username
                ),
                event_type="found_subs",
                details=(
                    f"нашёл {len(added)} подписок на "
                    f"{format_money(total_found_amount)}/мес"
                ),
                amount=total_found_amount,
            )
            session.add(social_event)

        await session.commit()

    # Формируем ответ
    if added:
        text = f"✅ <b>Найдено подписок: {len(added)}</b>\n\n"

        total_monthly = 0
        for sub_data in added:
            price = sub_data.get("price", 0)
            monthly = get_monthly_price(
                price,
                sub_data.get("billing_cycle", "monthly"),
            )
            total_monthly += monthly
            cat = SUBSCRIPTION_CATEGORIES.get(
                sub_data.get("category", "other"), "📦"
            )
            trial_mark = " 🆓" if sub_data.get("is_trial") else ""

            text += (
                f"• <b>{sub_data['name']}</b> — "
                f"{format_money(price)}/мес "
                f"({cat}){trial_mark}\n"
            )

        text += (
            f"\n💰 Итого: {format_money(total_monthly)}/мес "
            f"({format_money(total_monthly * 12)}/год)\n\n"
            f"📊 Оцени использование каждой подписки "
            f"в разделе «Мои подписки»"
        )

        if skipped:
            text += f"\n\n⏭ Пропущено: {', '.join(skipped)}"

    else:
        text = (
            "🤔 Подписки найдены, но не добавлены "
            "(дубликаты или слишком низкая уверенность).\n\n"
        )
        if skipped:
            text += f"Пропущено: {', '.join(skipped)}"

    await processing_msg.edit_text(
        text, reply_markup=back_to_menu_keyboard()
    )