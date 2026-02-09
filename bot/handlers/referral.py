"""👥 Реферальная система."""

import logging
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy import select, func

from bot.database import (
    async_session, User, UserAchievement,
)
from bot.utils.helpers import format_money
from bot.keyboards.inline import back_to_menu_keyboard
from bot.config import config

logger = logging.getLogger(__name__)
router = Router()


async def process_referral(
    referrer_tg_id: int,
    new_user_tg_id: int,
):
    """
    Обработка реферала — награждение пригласившего.
    Вызывается при регистрации нового пользователя.
    """
    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == referrer_tg_id
            )
        )
        referrer = result.scalar_one_or_none()

        if not referrer:
            return

        # Даём 30 дней Premium за каждого друга
        now = datetime.utcnow()
        if referrer.premium_until and referrer.premium_until > now:
            referrer.premium_until += timedelta(days=30)
        else:
            referrer.premium_until = now + timedelta(days=30)
            referrer.is_premium = True

        await session.commit()

    logger.info(
        f"Реферал: {referrer_tg_id} получил 30 дней Premium "
        f"за приглашение {new_user_tg_id}"
    )

    # Уведомляем реферера
    try:
        from bot.loader import bot
        await bot.send_message(
            chat_id=referrer_tg_id,
            text=(
                f"🎉 <b>Друг присоединился!</b>\n\n"
                f"Ты получил <b>30 дней Premium</b> бесплатно!\n"
                f"Premium активен до: "
                f"{referrer.premium_until.strftime('%d.%m.%Y')}\n\n"
                f"Приглашай ещё друзей "
                f"и получай Premium навсегда! 💎"
            ),
        )
    except Exception as e:
        logger.error(f"Referral notification error: {e}")


@router.callback_query(F.data == "referral")
@router.message(Command("ref"))
async def show_referral(event: Message | CallbackQuery):
    """Показать реферальную информацию."""
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

    # Считаем приглашённых
    async with async_session() as session:
        count_result = await session.execute(
            select(func.count(User.id)).where(
                User.referred_by == tg_id
            )
        )
        invited_count = count_result.scalar() or 0

    free_days = invited_count * 30
    bot_info = await (
        event.bot if isinstance(event, Message)
        else event.message.bot
    ).get_me()
    bot_username = bot_info.username

    ref_link = (
        f"https://t.me/{bot_username}"
        f"?start=ref_{user.referral_code}"
    )

    text = (
        f"👥 <b>ПРИГЛАСИ ДРУГА</b>\n\n"
        f"Как это работает:\n\n"
        f"1️⃣ Отправь другу ссылку ⬇️\n"
        f"2️⃣ Мы покажем ему, сколько денег он теряет\n"
        f"3️⃣ Он начнёт экономить\n"
        f"4️⃣ Ты получаешь <b>30 дней Premium</b> бесплатно!\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🔗 <b>Твоя ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"👥 Приглашено друзей: <b>{invited_count}</b>\n"
        f"🎁 Бесплатных дней заработано: <b>{free_days}</b>\n"
    )

    if user.premium_until:
        text += (
            f"⭐ Premium активен до: "
            f"<b>{user.premium_until.strftime('%d.%m.%Y')}</b>\n"
        )

    text += (
        f"\n💡 Это не спам — ты реально "
        f"помогаешь другу сэкономить деньги!"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📤 Поделиться ссылкой",
            switch_inline_query=(
                f"Я сэкономил {format_money(user.total_saved)}/мес "
                f"с SubKiller! Попробуй: {ref_link}"
            ),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Скопировать ссылку",
            callback_data="copy_ref_link",
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


@router.callback_query(F.data == "copy_ref_link")
async def copy_ref_link(callback: CallbackQuery):
    """Подсказка о копировании."""
    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(
                User.telegram_id == callback.from_user.id
            )
        )
        user = user_result.scalar_one_or_none()

    if user:
        bot_info = await callback.message.bot.get_me()
        ref_link = (
            f"https://t.me/{bot_info.username}"
            f"?start=ref_{user.referral_code}"
        )
        await callback.answer(
            "Нажми на ссылку в сообщении, чтобы скопировать!",
            show_alert=True,
        )
    else:
        await callback.answer("❌ Ошибка", show_alert=True)