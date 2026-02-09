"""💣 Калькулятор замен — поиск бесплатных альтернатив."""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select

from bot.database import (
    async_session, User, Subscription,
    SubscriptionStatus,
)
from bot.services.gigachat_service import gigachat_service
from bot.utils.helpers import format_money, get_monthly_price
from bot.keyboards.inline import back_to_menu_keyboard
from bot.config import ALTERNATIVES_DB

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "alternatives")
async def show_alternatives_list(callback: CallbackQuery):
    """Показать все подписки для поиска альтернатив."""
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
            ).order_by(Subscription.price.desc())
        )
        subs = list(result.scalars().all())

    if not subs:
        await callback.message.edit_text(
            "💣 <b>Калькулятор замен</b>\n\n"
            "Добавь подписки для поиска альтернатив.",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer()
        return

    text = (
        "💣 <b>КАЛЬКУЛЯТОР ЗАМЕН</b>\n\n"
        "Выбери подписку, чтобы найти "
        "бесплатную или дешёвую альтернативу:\n"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()

    for s in subs[:12]:
        m = get_monthly_price(s.price, s.billing_cycle)
        has_alt = s.name in ALTERNATIVES_DB
        icon = "💣" if has_alt else "🔍"
        builder.row(
            InlineKeyboardButton(
                text=f"{icon} {s.name} — {format_money(m)}/мес",
                callback_data=f"find_alt_{s.id}",
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


@router.callback_query(F.data.startswith("find_alt_"))
async def find_alternatives(callback: CallbackQuery):
    """Поиск альтернатив для конкретной подписки."""
    sub_id = int(callback.data.replace("find_alt_", ""))

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

        result = await session.execute(
            select(Subscription).where(
                Subscription.id == sub_id,
                Subscription.user_id == user.id,
            )
        )
        sub = result.scalar_one_or_none()

    if not sub:
        await callback.answer(
            "❌ Подписка не найдена", show_alert=True
        )
        return

    monthly = get_monthly_price(sub.price, sub.billing_cycle)

    # Сначала проверяем локальную базу
    local_alts = ALTERNATIVES_DB.get(sub.name, [])

    if not local_alts and user.is_premium:
        # Ищем через GigaChat (Premium)
        loading = await callback.message.edit_text(
            f"🔍 Ищу альтернативы для {sub.name}..."
        )

        try:
            local_alts = await gigachat_service.find_alternatives(
                service_name=sub.name,
                price=monthly,
                category=sub.category,
            )
        except Exception as e:
            logger.error(f"Alt search error: {e}")
            local_alts = []

    if not local_alts:
        text = (
            f"💣 <b>Альтернативы для {sub.name}</b>\n\n"
            f"Пока не нашёл альтернатив для этого сервиса.\n\n"
        )
        if not user.is_premium:
            text += (
                "⭐ С Premium я буду искать "
                "альтернативы через AI!"
            )

        await callback.message.edit_text(
            text, reply_markup=back_to_menu_keyboard()
        )
        await callback.answer()
        return

    text = (
        f"💣 <b>АЛЬТЕРНАТИВЫ</b>\n\n"
        f"<b>{sub.name}</b> "
        f"({format_money(monthly)}/мес):\n\n"
    )

    total_savings = 0

    for i, alt in enumerate(local_alts, 1):
        alt_price = alt.get("price", 0)
        coverage = alt.get("coverage", 50)
        url = alt.get("url", "")
        note = alt.get("note", "")

        savings = monthly - alt_price
        if savings > 0:
            total_savings = max(total_savings, savings)

        price_text = (
            "бесплатно" if alt_price == 0
            else f"{format_money(alt_price)}/мес"
        )

        # Прогресс-бар покрытия
        filled = coverage // 10
        empty = 10 - filled
        bar = "█" * filled + "░" * empty

        text += (
            f"{'├' if i < len(local_alts) else '└'} "
            f"<b>{alt['name']}</b> ({price_text})\n"
            f"{'│' if i < len(local_alts) else ' '} "
            f"  Покрытие: [{bar}] {coverage}%\n"
        )
        if note:
            text += (
                f"{'│' if i < len(local_alts) else ' '} "
                f"  💡 {note}\n"
            )
        if url:
            text += (
                f"{'│' if i < len(local_alts) else ' '} "
                f"  🔗 {url}\n"
            )
        text += "\n"

    if total_savings > 0:
        text += (
            f"💰 <b>Потенциальная экономия:</b>\n"
            f"   {format_money(total_savings)}/мес = "
            f"{format_money(total_savings * 12)}/год\n\n"
        )

    text += "Хочешь переключиться? Отмени текущую подписку:"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"❌ Отменить {sub.name}",
            callback_data=f"cancel_sub_{sub.id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="💣 Другие подписки",
            callback_data="alternatives",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Главное меню",
            callback_data="back_to_menu",
        )
    )

    try:
        await callback.message.edit_text(
            text, reply_markup=builder.as_markup()
        )
    except Exception:
        await callback.message.answer(
            text, reply_markup=builder.as_markup()
        )
    await callback.answer()