"""🔮 Предсказатель утечки денег + 📊 Дашборд здоровья."""

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
from bot.services.gigachat_service import gigachat_service
from bot.utils.helpers import (
    format_money, get_monthly_price,
    get_health_score, health_emoji,
)
from bot.keyboards.inline import back_to_menu_keyboard
from bot.config import SUBSCRIPTION_CATEGORIES

logger = logging.getLogger(__name__)
router = Router()


# ============== 🔮 Предсказатель ==============

@router.callback_query(F.data == "predictions")
async def show_predictions(callback: CallbackQuery):
    """Предсказатель утечки денег (Premium)."""
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
            "🔮 <b>Предсказатель утечки денег</b>\n\n"
            "Эта функция доступна в Premium.\n\n"
            "Я могу предсказать:\n"
            "• Какие подписки ты забросишь\n"
            "• Сколько денег потеряешь впустую\n"
            "• Когда лучше отменить подписку\n\n"
            "⭐ Подключи Premium за 490₽/мес"
        )
        from bot.keyboards.inline import premium_keyboard
        await callback.message.edit_text(
            text, reply_markup=premium_keyboard()
        )
        await callback.answer()
        return

    # Загружаем подписки
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
        await callback.message.edit_text(
            "🔮 <b>Предсказатель</b>\n\n"
            "Добавь подписки, чтобы я мог предсказать утечки.",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
        return

    loading_msg = await callback.message.edit_text(
        "🔮 Анализирую твои подписки...\n"
        "Предсказываю будущее... ⏳"
    )

    text = "🔮 <b>ПРЕДСКАЗАТЕЛЬ УТЕЧКИ ДЕНЕГ</b>\n\n"
    total_predicted_waste = 0

    for sub in subs:
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
            days_since_last_use = days_since_signup

        monthly = get_monthly_price(sub.price, sub.billing_cycle)

        try:
            prediction = (
                await gigachat_service.analyze_usage_prediction(
                    sub_name=sub.name,
                    days_since_signup=days_since_signup,
                    days_since_last_use=days_since_last_use,
                    monthly_price=monthly,
                )
            )
        except Exception as e:
            logger.error(f"Prediction error for {sub.name}: {e}")
            # Фоллбэк-предсказание
            abandon_prob = min(95, days_since_last_use * 2)
            prediction = {
                "will_abandon": days_since_last_use > 30,
                "probability_percent": abandon_prob,
                "predicted_waste_6months": monthly * 6,
                "recommendation": "Оцени использование",
                "reason": (
                    f"Не использовалось {days_since_last_use} дней"
                ),
            }

        prob = prediction.get("probability_percent", 50)
        waste = prediction.get(
            "predicted_waste_6months", monthly * 6
        )

        if prob >= 60:
            emoji = "🔴"
            total_predicted_waste += waste
        elif prob >= 40:
            emoji = "🟡"
            total_predicted_waste += waste * 0.5
        else:
            emoji = "🟢"

        text += (
            f"{emoji} <b>{sub.name}</b> "
            f"({format_money(monthly)}/мес)\n"
        )

        if prob >= 60:
            text += (
                f"   ⚠️ Вероятность забросить: <b>{prob}%</b>\n"
                f"   💸 Потеряешь за 6 мес: "
                f"<b>{format_money(waste)}</b>\n"
                f"   💡 {prediction.get('recommendation', '')}\n"
            )
        elif prob >= 40:
            text += (
                f"   ⚡ Риск: {prob}%\n"
                f"   💡 {prediction.get('recommendation', '')}\n"
            )
        else:
            text += f"   ✅ Вероятность забросить: {prob}% (низкая)\n"

        if prediction.get("reason"):
            text += f"   📝 {prediction['reason']}\n"
        text += "\n"

    if total_predicted_waste > 0:
        text += (
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"💸 <b>Прогноз потерь за 6 месяцев:</b>\n"
            f"<b>{format_money(total_predicted_waste)}</b>\n\n"
            f"❗ Отмени рисковые подписки, "
            f"пока не поздно!"
        )

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
            text="🔙 Главное меню",
            callback_data="back_to_menu",
        )
    )

    await loading_msg.edit_text(
        text, reply_markup=builder.as_markup()
    )
    await callback.answer()


# ============== 📊 Дашборд здоровья ==============

@router.callback_query(F.data == "health_dashboard")
@router.message(Command("report"))
@router.message(F.text == "📊 Отчёт")
async def show_health_dashboard(event: Message | CallbackQuery):
    """Дашборд подписочного здоровья."""
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
        active_subs = list(result.scalars().all())

        cancelled_result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == SubscriptionStatus.CANCELLED.value,
            )
        )
        cancelled_subs = list(cancelled_result.scalars().all())

    if not active_subs and not cancelled_subs:
        text = (
            "📊 <b>Дашборд здоровья</b>\n\n"
            "Добавь подписки, чтобы увидеть отчёт."
        )
        kb = back_to_menu_keyboard()
        if isinstance(event, CallbackQuery):
            await event.message.edit_text(text, reply_markup=kb)
            await event.answer()
        else:
            await event.answer(text, reply_markup=kb)
        return

    # Группируем подписки
    green = []  # Активно используемые
    yellow = []  # Редко
    red = []  # Не используемые
    unknown = []  # Не оценены

    total_monthly = 0
    wasted_monthly = 0

    for s in active_subs:
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
            unknown.append(s)
            wasted_monthly += monthly * 0.5

    # Расчёт оценки
    used_count = len(green) + len(yellow)
    score = get_health_score(
        len(active_subs), used_count,
        total_monthly, wasted_monthly,
    )
    h_emoji = health_emoji(score)

    text = f"📊 <b>ДАШБОРД ПОДПИСОЧНОГО ЗДОРОВЬЯ</b>\n\n"

    text += (
        f"💰 Общий бюджет подписок: "
        f"<b>{format_money(total_monthly)}/мес</b>\n\n"
    )

    # Зелёные
    if green:
        green_total = sum(
            get_monthly_price(s.price, s.billing_cycle) for s in green
        )
        text += (
            f"🟢 <b>Активно используешь</b> ({len(green)}): "
            f"{format_money(green_total)}\n"
        )
        for s in green:
            m = get_monthly_price(s.price, s.billing_cycle)
            text += f"   {s.name} ({format_money(m)})\n"
        text += "\n"

    # Жёлтые
    if yellow:
        yellow_total = sum(
            get_monthly_price(s.price, s.billing_cycle)
            for s in yellow
        )
        text += (
            f"🟡 <b>Редко используешь</b> ({len(yellow)}): "
            f"{format_money(yellow_total)}\n"
        )
        for s in yellow:
            m = get_monthly_price(s.price, s.billing_cycle)
            last_use = ""
            if s.last_used:
                days_ago = (date.today() - s.last_used).days
                last_use = f" — {days_ago} дн. назад"
            text += f"   {s.name} ({format_money(m)}){last_use}\n"
        text += "\n"

    # Красные
    if red:
        red_total = sum(
            get_monthly_price(s.price, s.billing_cycle) for s in red
        )
        text += (
            f"🔴 <b>Не используешь</b> ({len(red)}): "
            f"{format_money(red_total)}\n"
        )
        for s in red:
            m = get_monthly_price(s.price, s.billing_cycle)
            text += f"   ❌ {s.name} ({format_money(m)})\n"
        text += "\n"

    # Не оценены
    if unknown:
        unknown_total = sum(
            get_monthly_price(s.price, s.billing_cycle)
            for s in unknown
        )
        text += (
            f"⚪ <b>Не оценено</b> ({len(unknown)}): "
            f"{format_money(unknown_total)}\n"
        )
        for s in unknown:
            m = get_monthly_price(s.price, s.billing_cycle)
            text += f"   ❓ {s.name} ({format_money(m)})\n"
        text += "\n"

    # Оценка здоровья
    bar_filled = score // 10
    bar_empty = 10 - bar_filled
    bar = "█" * bar_filled + "░" * bar_empty

    text += (
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"Оценка здоровья: <b>{score}/100</b> {h_emoji}\n"
        f"[{bar}]\n\n"
    )

    if wasted_monthly > 0:
        pct = int(wasted_monthly / total_monthly * 100) if total_monthly > 0 else 0
        text += (
            f"⚠️ Ты переплачиваешь <b>{pct}%</b> "
            f"({format_money(wasted_monthly)}/мес)\n\n"
        )

    # Потенциальная экономия
    potential_savings = wasted_monthly
    if potential_savings > 0:
        text += (
            f"💡 <b>Потенциальная экономия:</b>\n"
            f"• {format_money(potential_savings)}/мес\n"
            f"• {format_money(potential_savings * 12)}/год 🎉\n"
        )

    # Кнопки
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()

    if red or unknown:
        builder.row(
            InlineKeyboardButton(
                text="❌ Отключить ненужные",
                callback_data="my_subscriptions",
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="💣 Найти альтернативы",
            callback_data="alternatives",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔮 Предсказатель утечки",
            callback_data="predictions",
        ),
        InlineKeyboardButton(
            text="🧬 ДНК профиль",
            callback_data="dna_profile",
        ),
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