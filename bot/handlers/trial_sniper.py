"""🤖 Автоснайпер Trial — управление пробными периодами."""

import logging
from datetime import date, datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select

from bot.database import (
    async_session, User, Subscription,
    SubscriptionStatus, UsageLevel, BillingCycle,
    Notification, NotificationType,
)
from bot.utils.helpers import (
    format_money, get_next_billing_date, days_until,
)
from bot.keyboards.inline import back_to_menu_keyboard

logger = logging.getLogger(__name__)
router = Router()

# Доступные trial-подписки (обновлять по мере необходимости)
AVAILABLE_TRIALS = [
    {
        "name": "YouTube Premium",
        "duration_days": 30,
        "price_after": 399,
        "url": "https://youtube.com/premium",
    },
    {
        "name": "Spotify Premium",
        "duration_days": 30,
        "price_after": 199,
        "url": "https://spotify.com/premium",
    },
    {
        "name": "Canva Pro",
        "duration_days": 30,
        "price_after": 999,
        "url": "https://canva.com/pro",
    },
    {
        "name": "Notion AI",
        "duration_days": 7,
        "price_after": 800,
        "url": "https://notion.so",
    },
    {
        "name": "LinkedIn Premium",
        "duration_days": 30,
        "price_after": 800,
        "url": "https://linkedin.com/premium",
    },
    {
        "name": "Headspace",
        "duration_days": 14,
        "price_after": 499,
        "url": "https://headspace.com",
    },
    {
        "name": "Duolingo Plus",
        "duration_days": 14,
        "price_after": 699,
        "url": "https://duolingo.com",
    },
    {
        "name": "Adobe Creative Cloud",
        "duration_days": 7,
        "price_after": 1500,
        "url": "https://adobe.com",
    },
    {
        "name": "Figma Professional",
        "duration_days": 30,
        "price_after": 1200,
        "url": "https://figma.com",
    },
    {
        "name": "ChatGPT Plus",
        "duration_days": 0,
        "price_after": 2050,
        "url": "https://chat.openai.com",
        "note": "Нет бесплатного trial, но бесплатная версия доступна",
    },
]


class TrialSniperStates(StatesGroup):
    waiting_trial_name = State()


@router.callback_query(F.data == "trial_sniper")
async def show_trial_sniper(callback: CallbackQuery):
    """Показать автоснайпер триалов (Premium)."""
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
            "🤖 <b>Автоснайпер Trial</b>\n\n"
            "Я помогу тебе:\n"
            "• Найти бесплатные trial-периоды\n"
            "• Поставить таймер автоотмены\n"
            "• Напомнить за 1 день до конца trial\n\n"
            "⭐ Доступно в Premium"
        )
        from bot.keyboards.inline import premium_keyboard
        await callback.message.edit_text(
            text, reply_markup=premium_keyboard()
        )
        await callback.answer()
        return

    # Получаем текущие trial-подписки
    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.is_trial == True,
                Subscription.status == SubscriptionStatus.TRIAL.value,
            )
        )
        active_trials = list(result.scalars().all())

    text = "🤖 <b>АВТОСНАЙПЕР TRIAL</b>\n\n"

    # Текущие триалы
    if active_trials:
        text += "📋 <b>Активные trial-подписки:</b>\n\n"
        for t in active_trials:
            d = 0
            if t.trial_end_date:
                d = days_until(t.trial_end_date)
            status = "✅ Активен" if d > 0 else "⚠️ Истекает"
            text += (
                f"🎯 <b>{t.name}</b>\n"
                f"   Trial: {d} дн. осталось\n"
                f"   Статус: {status}\n"
                f"   ⏰ Автоотмена: "
                f"{'ДА ✅' if t.auto_cancel_trial else 'НЕТ ❌'}\n"
                f"   Цена после trial: "
                f"{format_money(t.price)}/мес\n\n"
            )
        text += "━━━━━━━━━━━━━━━━━━\n\n"

    # Доступные триалы
    text += "🆓 <b>Доступные бесплатные trial:</b>\n\n"

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()

    for trial in AVAILABLE_TRIALS:
        if trial["duration_days"] == 0:
            continue

        # Проверяем, нет ли уже такой подписки
        has_already = any(
            t.name == trial["name"] for t in active_trials
        )
        if has_already:
            continue

        text += (
            f"→ <b>{trial['name']}</b> "
            f"({trial['duration_days']} дн. бесплатно)\n"
            f"   Цена после: {format_money(trial['price_after'])}/мес\n"
        )

        builder.row(
            InlineKeyboardButton(
                text=f"🎯 {trial['name']} ({trial['duration_days']} дн.)",
                callback_data=f"activate_trial_{trial['name']}",
            )
        )

    text += (
        "\n💡 Я напомню за 1 день до окончания trial, "
        "чтобы ты НЕ ЗАПЛАТИЛ ни копейки!"
    )

    builder.row(
        InlineKeyboardButton(
            text="📝 Добавить свой trial",
            callback_data="custom_trial",
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


@router.callback_query(F.data.startswith("activate_trial_"))
async def activate_trial(callback: CallbackQuery):
    """Активация отслеживания trial."""
    trial_name = callback.data.replace("activate_trial_", "")

    trial_data = None
    for t in AVAILABLE_TRIALS:
        if t["name"] == trial_name:
            trial_data = t
            break

    if not trial_data:
        await callback.answer(
            "❌ Trial не найден", show_alert=True
        )
        return

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

        trial_end = date.today() + timedelta(
            days=trial_data["duration_days"]
        )

        sub = Subscription(
            user_id=user.id,
            name=trial_data["name"],
            price=trial_data["price_after"],
            category="other",
            billing_cycle=BillingCycle.MONTHLY.value,
            next_billing_date=trial_end,
            is_trial=True,
            trial_end_date=trial_end,
            auto_cancel_trial=True,
            status=SubscriptionStatus.TRIAL.value,
            usage_level=UsageLevel.UNKNOWN.value,
        )
        session.add(sub)

        # Уведомление за 1 день
        reminder_date = datetime.combine(
            trial_end - timedelta(days=1),
            datetime.min.time().replace(hour=10),
        )
        notif = Notification(
            user_id=user.id,
            notification_type=NotificationType.TRIAL_ENDING.value,
            message=(
                f"🆓⚠️ Trial {trial_data['name']} "
                f"заканчивается завтра!\n"
                f"После этого спишется "
                f"{format_money(trial_data['price_after'])}/мес.\n"
                f"Продлить или отменить?"
            ),
            scheduled_at=reminder_date,
        )
        session.add(notif)

        # Уведомление за 2 дня
        if trial_data["duration_days"] > 3:
            reminder_2d = datetime.combine(
                trial_end - timedelta(days=2),
                datetime.min.time().replace(hour=10),
            )
            notif_2d = Notification(
                user_id=user.id,
                notification_type=NotificationType.TRIAL_ENDING.value,
                message=(
                    f"⏰ {trial_data['name']}: "
                    f"trial заканчивается через 2 дня!"
                ),
                scheduled_at=reminder_2d,
            )
            session.add(notif_2d)

        await session.commit()
        await session.refresh(sub)

    text = (
        f"🎯 <b>Автоснайпер активирован!</b>\n\n"
        f"Сервис: <b>{trial_data['name']}</b>\n"
        f"Trial: {trial_data['duration_days']} дней бесплатно\n"
        f"Окончание: {trial_end.strftime('%d.%m.%Y')}\n\n"
        f"⏰ Напомню за 2 дня и за 1 день до списания\n"
        f"Ты <b>НЕ ЗАПЛАТИШЬ</b> ни копейки, "
        f"если не захочешь!\n\n"
        f"🔗 Подпишись здесь: {trial_data.get('url', '')}"
    )

    await callback.message.edit_text(
        text, reply_markup=back_to_menu_keyboard()
    )
    await callback.answer("✅ Trial активирован!")


@router.callback_query(F.data == "custom_trial")
async def custom_trial_prompt(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Добавить свой trial."""
    await callback.message.edit_text(
        "📝 <b>Добавить свой trial</b>\n\n"
        "Введи название сервиса, "
        "на который ты подписался на пробный период:"
    )
    await state.set_state(TrialSniperStates.waiting_trial_name)
    await callback.answer()


@router.message(
    F.text,
    TrialSniperStates.waiting_trial_name,
)
async def process_custom_trial_name(
    message: Message,
    state: FSMContext,
):
    """Обработка имени custom trial — переход в FSM подписки."""
    name = message.text.strip()

    from bot.handlers.subscriptions import AddSubStates
    await state.update_data(name=name, is_trial=True)
    await message.answer(
        f"🆓 Trial: <b>{name}</b>\n\n"
        "Введи цену, которая будет после trial (₽/мес):"
    )
    await state.set_state(AddSubStates.waiting_price)