"""⭐ Premium — подписка через YooKassa."""

import logging
import uuid
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    LabeledPrice, PreCheckoutQuery,
)
from aiogram.filters import Command
from sqlalchemy import select

from bot.database import (
    async_session, User, Payment, PaymentStatus,
)
from bot.utils.helpers import format_money
from bot.keyboards.inline import (
    premium_keyboard, back_to_menu_keyboard,
)
from bot.config import config
from bot.services.payment_service import payment_service

logger = logging.getLogger(__name__)
router = Router()


# ============== Информация о Premium ==============

@router.callback_query(F.data == "premium_info")
@router.message(Command("premium"))
@router.message(F.text == "⭐ Premium")
async def show_premium_info(event: Message | CallbackQuery):
    """Информация о Premium."""
    tg_id = event.from_user.id

    async with async_session() as session:
        user_result = await session.execute(
            select(User).where(User.telegram_id == tg_id)
        )
        user = user_result.scalar_one_or_none()

    is_premium = user.is_premium if user else False
    premium_until = user.premium_until if user else None

    if is_premium and premium_until:
        text = (
            f"⭐ <b>Premium активен!</b>\n\n"
            f"📅 До: <b>"
            f"{premium_until.strftime('%d.%m.%Y')}</b>\n\n"
            f"Тебе доступно:\n"
            f"• 🔮 Предсказатель утечки денег\n"
            f"• 🧬 ДНК-профиль подписчика\n"
            f"• 💣 AI-калькулятор замен\n"
            f"• 🤖 Автоснайпер Trial\n"
            f"• 🔔 Умные напоминания\n"
            f"• 📊 Детальный дашборд здоровья\n"
            f"• 🎰 Инвестиционный калькулятор\n"
            f"• 🏅 Все ачивки и челленджи\n"
        )
        kb = back_to_menu_keyboard()
    else:
        trial_used = (
            user.premium_trial_used if user else False
        )
        text = (
            f"⭐ <b>SubKiller Premium</b>\n\n"
            f"<b>{config.premium.price}₽/мес</b>\n\n"
            f"🆓 <b>Бесплатно:</b>\n"
            f"• Добавление подписок\n"
            f"• Базовый счётчик боли\n"
            f"• Рейтинг экономии\n"
            f"• 3 ачивки\n\n"
            f"⭐ <b>Premium:</b>\n"
            f"• 🔮 Предсказатель утечки — AI анализирует, "
            f"какие подписки ты забросишь\n"
            f"• 🧬 ДНК-профиль — узнай свой тип подписчика\n"
            f"• 💣 AI-замены — бесплатные альтернативы "
            f"через нейросеть\n"
            f"• 🤖 Автоснайпер Trial — бесплатные "
            f"пробные периоды без риска\n"
            f"• 🔔 Умные напоминания — за 3, 1 день "
            f"до списания\n"
            f"• 📊 Детальный отчёт здоровья\n"
            f"• 🎰 Инвестиционный калькулятор\n"
            f"• 🏅 Все 17 ачивок\n"
            f"• 🎯 Приоритетная поддержка\n\n"
            f"💡 <b>Окупается за 1 отменённую подписку!</b>\n"
        )

        if not trial_used:
            text += (
                f"\n🎁 <b>Попробуй "
                f"{config.premium.trial_days} дней бесплатно!</b>"
            )

        kb = premium_keyboard()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)


@router.callback_query(F.data == "premium_status")
async def premium_status(callback: CallbackQuery):
    """Статус Premium."""
    await show_premium_info(callback)


# ============== Бесплатный trial ==============

@router.callback_query(F.data == "try_premium_trial")
async def try_premium_trial(callback: CallbackQuery):
    """Активация бесплатного trial Premium."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == callback.from_user.id
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer(
                "❌ /start", show_alert=True
            )
            return

        if user.premium_trial_used:
            await callback.answer(
                "❌ Ты уже использовал бесплатный период!",
                show_alert=True,
            )
            return

        if user.is_premium:
            await callback.answer(
                "⭐ Premium уже активен!",
                show_alert=True,
            )
            return

        # Активируем trial
        now = datetime.utcnow()
        user.is_premium = True
        user.premium_until = now + timedelta(
            days=config.premium.trial_days
        )
        user.premium_trial_used = True
        await session.commit()

    text = (
        f"🎉 <b>Premium активирован!</b>\n\n"
        f"⭐ Бесплатный период: "
        f"<b>{config.premium.trial_days} дней</b>\n"
        f"📅 До: <b>"
        f"{user.premium_until.strftime('%d.%m.%Y')}</b>\n\n"
        f"Теперь тебе доступны все функции:\n"
        f"• 🔮 Предсказатель\n"
        f"• 🧬 ДНК-профиль\n"
        f"• 💣 AI-замены\n"
        f"• 🤖 Автоснайпер Trial\n"
        f"• 🔔 Умные напоминания\n\n"
        f"Попробуй прямо сейчас! ⬇️"
    )

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔮 Предсказатель",
            callback_data="predictions",
        ),
        InlineKeyboardButton(
            text="🧬 ДНК",
            callback_data="dna_profile",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🤖 Автоснайпер",
            callback_data="trial_sniper",
        ),
        InlineKeyboardButton(
            text="💣 Замены",
            callback_data="alternatives",
        ),
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
    await callback.answer("🎉 Premium активирован!")


# ============== Покупка через YooKassa ==============

@router.callback_query(F.data == "buy_premium")
async def buy_premium(callback: CallbackQuery):
    """Создание платежа через YooKassa."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == callback.from_user.id
            )
        )
        user = result.scalar_one_or_none()

    if not user:
        await callback.answer("❌ /start", show_alert=True)
        return

    if user.is_premium:
        await callback.answer(
            "⭐ Premium уже активен!", show_alert=True
        )
        return

    try:
        payment_url, payment_id = (
            await payment_service.create_payment(
                amount=config.premium.price,
                user_id=user.id,
                telegram_id=callback.from_user.id,
                description="SubKiller Premium — 1 месяц",
            )
        )

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text=f"💳 Оплатить {config.premium.price}₽",
                url=payment_url,
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="✅ Я оплатил",
                callback_data=f"check_payment_{payment_id}",
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="premium_info",
            )
        )

        await callback.message.edit_text(
            f"💳 <b>Оплата Premium</b>\n\n"
            f"Сумма: <b>{config.premium.price}₽</b>\n"
            f"Период: <b>1 месяц</b>\n\n"
            f"Нажми кнопку для оплаты через ЮKassa:",
            reply_markup=builder.as_markup(),
        )

    except Exception as e:
        logger.error(f"Payment creation error: {e}")
        await callback.message.edit_text(
            "❌ Ошибка создания платежа. "
            "Попробуй позже.",
            reply_markup=back_to_menu_keyboard(),
        )

    await callback.answer()


@router.callback_query(F.data.startswith("check_payment_"))
async def check_payment(callback: CallbackQuery):
    """Проверка статуса платежа."""
    payment_id = callback.data.replace("check_payment_", "")

    try:
        is_paid = await payment_service.check_payment(payment_id)
    except Exception as e:
        logger.error(f"Payment check error: {e}")
        await callback.answer(
            "❌ Ошибка проверки. Попробуй ещё раз.",
            show_alert=True,
        )
        return

    if is_paid:
        # Активируем Premium
        async with async_session() as session:
            result = await session.execute(
                select(User).where(
                    User.telegram_id == callback.from_user.id
                )
            )
            user = result.scalar_one_or_none()

            if user:
                now = datetime.utcnow()
                if (
                    user.premium_until
                    and user.premium_until > now
                ):
                    user.premium_until += timedelta(days=30)
                else:
                    user.premium_until = now + timedelta(days=30)
                user.is_premium = True

                # Обновляем платёж
                pay_result = await session.execute(
                    select(Payment).where(
                        Payment.yookassa_payment_id == payment_id
                    )
                )
                payment = pay_result.scalar_one_or_none()
                if payment:
                    payment.status = PaymentStatus.SUCCEEDED.value
                    payment.confirmed_at = now

                await session.commit()

        await callback.message.edit_text(
            f"🎉 <b>Premium активирован!</b>\n\n"
            f"⭐ Спасибо за покупку!\n"
            f"📅 Активен до: "
            f"<b>"
            f"{user.premium_until.strftime('%d.%m.%Y')}"
            f"</b>\n\n"
            f"Все функции теперь доступны!",
            reply_markup=back_to_menu_keyboard(),
        )
        await callback.answer("🎉 Оплата прошла!")

    else:
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="🔄 Проверить ещё раз",
                callback_data=f"check_payment_{payment_id}",
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="premium_info",
            )
        )

        await callback.answer(
            "⏳ Платёж ещё не подтверждён. "
            "Подожди немного.",
            show_alert=True,
        )