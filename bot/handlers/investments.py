"""🎰 Калькулятор «А если бы инвестировал»."""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select

from bot.database import (
    async_session, User, Subscription,
    SubscriptionStatus, UsageLevel,
)
from bot.utils.helpers import (
    format_money, get_monthly_price,
    calculate_investment_return, get_comparable_purchase,
)
from bot.keyboards.inline import back_to_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "investments")
async def show_investments(callback: CallbackQuery):
    """Калькулятор инвестиций вместо подписок."""
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
            "🎰 <b>Инвестиционный калькулятор</b>\n\n"
            "Добавь подписки, чтобы увидеть, "
            "как деньги могли бы работать на тебя!",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
        return

    # Считаем потерянные деньги
    wasted_monthly = 0
    total_monthly = 0

    for s in subs:
        monthly = get_monthly_price(s.price, s.billing_cycle)
        total_monthly += monthly
        if s.usage_level in (
            UsageLevel.LOW.value,
            UsageLevel.NONE.value,
        ):
            wasted_monthly += monthly
        elif s.usage_level == UsageLevel.UNKNOWN.value:
            wasted_monthly += monthly * 0.5

    if wasted_monthly <= 0:
        wasted_monthly = total_monthly * 0.3

    # S&P 500 (средняя ~10% годовых)
    sp500_1y = calculate_investment_return(
        wasted_monthly, 1, 0.10
    )
    sp500_5y = calculate_investment_return(
        wasted_monthly, 5, 0.10
    )
    sp500_10y = calculate_investment_return(
        wasted_monthly, 10, 0.10
    )
    sp500_20y = calculate_investment_return(
        wasted_monthly, 20, 0.10
    )

    # Депозит (средняя ~8% годовых)
    deposit_1y = calculate_investment_return(
        wasted_monthly, 1, 0.08
    )
    deposit_5y = calculate_investment_return(
        wasted_monthly, 5, 0.08
    )
    deposit_10y = calculate_investment_return(
        wasted_monthly, 10, 0.08
    )

    # Crypto (условно ~30% годовых)
    crypto_5y = calculate_investment_return(
        wasted_monthly, 5, 0.30
    )

    comparable_5 = get_comparable_purchase(sp500_5y)
    comparable_10 = get_comparable_purchase(sp500_10y)
    comparable_20 = get_comparable_purchase(sp500_20y)

    text = (
        f"🎰 <b>ЧТО ЕСЛИ БЫ ТЫ ИНВЕСТИРОВАЛ ЭТИ ДЕНЬГИ?</b>\n\n"
        f"Ты тратишь на сомнительные подписки:\n"
        f"<b>{format_money(wasted_monthly)}/мес</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📈 <b>Индекс S&P 500</b> (~10% годовых):\n"
        f"   Через 1 год:   <b>{format_money(sp500_1y)}</b>\n"
        f"   Через 5 лет:   <b>{format_money(sp500_5y)}</b> "
        f"= {comparable_5}\n"
        f"   Через 10 лет:  <b>{format_money(sp500_10y)}</b> "
        f"= {comparable_10}\n"
        f"   Через 20 лет:  <b>{format_money(sp500_20y)}</b> "
        f"= {comparable_20}\n\n"
        f"🏦 <b>Банковский депозит</b> (~8% годовых):\n"
        f"   Через 1 год:   <b>{format_money(deposit_1y)}</b>\n"
        f"   Через 5 лет:   <b>{format_money(deposit_5y)}</b>\n"
        f"   Через 10 лет:  <b>{format_money(deposit_10y)}</b>\n\n"
        f"₿ <b>Криптовалюта</b> (~30% годовых*):\n"
        f"   Через 5 лет:   <b>{format_money(crypto_5y)}</b>\n"
        f"   <i>*высокий риск, условная доходность</i>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"😱 <b>Чувствуешь боль?</b>\n"
        f"Отключи подписки сейчас и начни инвестировать!"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="❌ Отключить подписки",
            callback_data="my_subscriptions",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💀 Счётчик боли",
            callback_data="pain_counter",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Главное меню",
            callback_data="back_to_menu",
        )
    )

    await callback.message.edit_text(
        text, reply_markup=builder.as_markup()
    )
    await callback.answer()