"""🧬 ДНК-профиль подписчика."""

import logging
from datetime import datetime

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, func

from bot.database import (
    async_session, User, Subscription,
    SubscriptionStatus, UsageLevel,
)
from bot.services.gigachat_service import gigachat_service
from bot.utils.helpers import format_money, get_monthly_price
from bot.keyboards.inline import back_to_menu_keyboard
from bot.config import SUBSCRIBER_TYPES

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "dna_profile")
async def show_dna_profile(callback: CallbackQuery):
    """Показать ДНК-профиль подписчика (Premium)."""
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

    if not user.is_premium:
        text = (
            "🧬 <b>ДНК-профиль подписчика</b>\n\n"
            "Узнай свой тип подписчика!\n\n"
            "Я определю:\n"
            "• Твой поведенческий тип\n"
            "• Зоны риска\n"
            "• Персональные рекомендации\n\n"
            "⭐ Доступно в Premium"
        )
        from bot.keyboards.inline import premium_keyboard
        await callback.message.edit_text(
            text, reply_markup=premium_keyboard()
        )
        await callback.answer()
        return

    # Собираем данные
    async with async_session() as session:
        all_subs = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id
            )
        )
        subs = list(all_subs.scalars().all())

    if len(subs) < 1:
        await callback.message.edit_text(
            "🧬 <b>ДНК-профиль</b>\n\n"
            "Добавь хотя бы 1 подписку для анализа.",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
        return

    loading_msg = await callback.message.edit_text(
        "🧬 Анализирую твой профиль...\n"
        "Секвенирую ДНК подписок... 🔬"
    )

    active = [
        s for s in subs
        if s.status in (
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIAL.value,
        )
    ]
    cancelled = [
        s for s in subs
        if s.status == SubscriptionStatus.CANCELLED.value
    ]
    trials = [s for s in subs if s.is_trial]

    total_monthly = sum(
        get_monthly_price(s.price, s.billing_cycle)
        for s in active
    )

    avg_age = 0
    if subs:
        ages = [
            (datetime.utcnow() - s.created_at).days for s in subs
        ]
        avg_age = sum(ages) / len(ages)

    # Паттерн использования
    high_use = sum(
        1 for s in active
        if s.usage_level == UsageLevel.HIGH.value
    )
    low_use = sum(
        1 for s in active
        if s.usage_level in (
            UsageLevel.LOW.value,
            UsageLevel.NONE.value,
        )
    )
    usage_pct = (
        int(high_use / len(active) * 100)
        if active else 0
    )
    usage_pattern = (
        f"Активно использует {usage_pct}% подписок. "
        f"{high_use} активных, {low_use} не используемых."
    )

    try:
        dna_result = await gigachat_service.get_subscriber_dna(
            total_subs=len(subs),
            active_subs=len(active),
            cancelled_subs=len(cancelled),
            trial_subs=len(trials),
            avg_sub_age_days=avg_age,
            total_monthly_spend=total_monthly,
            usage_pattern=usage_pattern,
        )
    except Exception as e:
        logger.error(f"DNA profile error: {e}")
        dna_result = {
            "type": "impulse_collector",
            "description": (
                "Ты любишь пробовать новое "
                "и часто подписываешься на эмоциях."
            ),
            "risk_zones": ["Бесплатные пробные периоды"],
            "tip": "Ставь напоминания об окончании trial.",
        }

    # Получаем данные типа
    sub_type_key = dna_result.get("type", "impulse_collector")
    type_data = SUBSCRIBER_TYPES.get(
        sub_type_key,
        SUBSCRIBER_TYPES["impulse_collector"],
    )

    # Сохраняем тип
    async with async_session() as session:
        user_result_db = await session.execute(
            select(User).where(
                User.telegram_id == callback.from_user.id
            )
        )
        db_user = user_result_db.scalar_one()
        db_user.subscriber_type = sub_type_key
        await session.commit()

    text = (
        f"🧬 <b>ТВОЙ ПРОФИЛЬ ПОДПИСЧИКА</b>\n\n"
        f"Тип: {type_data['emoji']} "
        f"<b>«{type_data['name']}»</b>\n\n"
        f"📝 {dna_result.get('description', type_data['description'])}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Активных подписок: {len(active)}\n"
        f"• Отменённых: {len(cancelled)}\n"
        f"• Пробных периодов: {len(trials)}\n"
        f"• Используешь реально: {usage_pct}%\n"
        f"• Трата в месяц: {format_money(total_monthly)}\n\n"
    )

    # Зоны риска
    risk_zones = dna_result.get("risk_zones", [])
    if risk_zones:
        text += "⚠️ <b>Зоны риска:</b>\n"
        for rz in risk_zones:
            text += f"   • {rz}\n"
        text += "\n"

    # Триалы-ловушки
    active_trials = [
        s for s in active
        if s.is_trial and s.trial_end_date
    ]
    if active_trials:
        text += "🆓 <b>Активные trial-подписки:</b>\n"
        for t in active_trials:
            from bot.utils.helpers import days_until
            d = days_until(t.trial_end_date)
            abandon_prob = max(50, 95 - d * 5)
            text += (
                f"   • {t.name} — заканчивается через {d} дн.\n"
                f"     ВЕРОЯТНОСТЬ забыть отписаться: "
                f"<b>{abandon_prob}%</b>\n"
            )
        text += "\n"

    # Совет
    tip = dna_result.get("tip", "")
    if tip:
        text += f"💡 <b>Совет:</b> {tip}\n\n"

    text += (
        "🔗 <i>Поделись своим профилем — "
        "это как гороскоп, только про деньги!</i>"
    )

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
            text="🔮 Предсказатель",
            callback_data="predictions",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Главное меню",
            callback_data="back_to_menu",
        )
    )

    await loading_msg.edit_text(
        text, reply_markup=builder.as_markup()
    )
    await callback.answer()