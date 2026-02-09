"""CRUD-управление подписками и FSM-сценарии."""

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import select, func

from bot.loader import bot
from bot.database import (
    async_session, User, Subscription,
    SubscriptionStatus, UsageLevel, BillingCycle,
    GlobalStats, SocialProofEvent, Notification,
    NotificationType,
)
from bot.keyboards.inline import (
    add_subscription_keyboard,
    categories_keyboard,
    popular_subs_keyboard,
    billing_cycle_keyboard,
    usage_level_keyboard,
    subscription_actions_keyboard,
    confirm_cancel_keyboard,
    back_to_menu_keyboard,
    main_menu_keyboard,
)
from bot.utils.helpers import (
    format_money, get_monthly_price,
    billing_cycle_name, get_next_billing_date,
    days_until, mask_username,
)
from bot.config import (
    config, SUBSCRIPTION_CATEGORIES, POPULAR_SUBSCRIPTIONS,
)

logger = logging.getLogger(__name__)
router = Router()


# ============== FSM States ==============

class AddSubStates(StatesGroup):
    """Состояния добавления подписки."""
    waiting_name = State()
    waiting_price = State()
    waiting_cycle = State()
    waiting_category = State()
    waiting_next_billing = State()
    waiting_usage = State()
    confirm = State()


class EditSubStates(StatesGroup):
    """Состояния редактирования подписки."""
    waiting_field = State()
    waiting_new_value = State()


# ============== Helpers ==============

async def get_user_by_tg_id(telegram_id: int) -> Optional[User]:
    """Получить пользователя по telegram_id."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def get_user_subscriptions(
    user_id: int,
    status: Optional[str] = None,
) -> list[Subscription]:
    """Получить подписки пользователя."""
    async with async_session() as session:
        query = select(Subscription).where(
            Subscription.user_id == user_id
        )
        if status:
            query = query.where(Subscription.status == status)
        query = query.order_by(Subscription.price.desc())
        result = await session.execute(query)
        return list(result.scalars().all())


def format_subscription_card(sub: Subscription) -> str:
    """Форматирование карточки подписки."""
    status_emoji = {
        SubscriptionStatus.ACTIVE.value: "🟢",
        SubscriptionStatus.CANCELLED.value: "❌",
        SubscriptionStatus.TRIAL.value: "🆓",
        SubscriptionStatus.PAUSED.value: "⏸",
    }

    usage_emoji = {
        UsageLevel.HIGH.value: "🟢",
        UsageLevel.MEDIUM.value: "🟡",
        UsageLevel.LOW.value: "🟠",
        UsageLevel.NONE.value: "🔴",
        UsageLevel.UNKNOWN.value: "⚪",
    }

    usage_text = {
        UsageLevel.HIGH.value: "Активно",
        UsageLevel.MEDIUM.value: "Иногда",
        UsageLevel.LOW.value: "Редко",
        UsageLevel.NONE.value: "Не использую",
        UsageLevel.UNKNOWN.value: "Не оценено",
    }

    s_emoji = status_emoji.get(sub.status, "⚪")
    u_emoji = usage_emoji.get(sub.usage_level, "⚪")
    u_text = usage_text.get(sub.usage_level, "?")
    category_name = SUBSCRIPTION_CATEGORIES.get(
        sub.category, "📦 Другое"
    )
    monthly = get_monthly_price(sub.price, sub.billing_cycle)

    card = (
        f"{s_emoji} <b>{sub.name}</b>\n"
        f"   💰 {format_money(sub.price)} "
        f"({billing_cycle_name(sub.billing_cycle)})\n"
        f"   📅 В месяц: {format_money(monthly)}\n"
        f"   📁 {category_name}\n"
        f"   {u_emoji} Использование: {u_text}\n"
    )

    if sub.next_billing_date:
        days_left = days_until(sub.next_billing_date)
        if days_left >= 0:
            card += f"   ⏰ Следующее списание: через {days_left} дн.\n"
        else:
            card += f"   ⏰ Списание просрочено\n"

    if sub.is_trial and sub.trial_end_date:
        trial_days = days_until(sub.trial_end_date)
        if trial_days > 0:
            card += f"   🆓 Trial: {trial_days} дн. осталось\n"
        else:
            card += f"   🆓 Trial истёк\n"

    return card


# ============== Показ подписок ==============

@router.callback_query(F.data == "my_subscriptions")
@router.message(Command("subs"))
async def show_subscriptions(
    event: Message | CallbackQuery,
):
    """Показать все подписки пользователя."""
    tg_id = event.from_user.id
    user = await get_user_by_tg_id(tg_id)

    if not user:
        text = "❌ Сначала используй /start"
        if isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
        else:
            await event.answer(text)
        return

    subs = await get_user_subscriptions(user.id)

    if not subs:
        text = (
            "📋 <b>Мои подписки</b>\n\n"
            "У тебя пока нет добавленных подписок.\n\n"
            "Добавь их, чтобы я помог найти утечки денег! 💸"
        )
        kb = add_subscription_keyboard()
    else:
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

        total_monthly = sum(
            get_monthly_price(s.price, s.billing_cycle)
            for s in active
        )
        total_yearly = total_monthly * 12

        text = (
            f"📋 <b>Мои подписки</b> ({len(active)} активных)\n\n"
        )

        # Группировка по использованию
        used = [
            s for s in active
            if s.usage_level in (
                UsageLevel.HIGH.value,
                UsageLevel.MEDIUM.value,
            )
        ]
        unused = [
            s for s in active
            if s.usage_level in (
                UsageLevel.LOW.value,
                UsageLevel.NONE.value,
            )
        ]
        unknown = [
            s for s in active
            if s.usage_level == UsageLevel.UNKNOWN.value
        ]

        if used:
            text += "✅ <b>Используешь:</b>\n"
            for s in used:
                text += format_subscription_card(s)
                text += "\n"

        if unused:
            wasted = sum(
                get_monthly_price(s.price, s.billing_cycle)
                for s in unused
            )
            text += f"⚠️ <b>Не используешь</b> (−{format_money(wasted)}/мес):\n"
            for s in unused:
                text += format_subscription_card(s)
                text += "\n"

        if unknown:
            text += "❓ <b>Не оценено:</b>\n"
            for s in unknown:
                text += format_subscription_card(s)
                text += "\n"

        text += (
            f"\n💰 <b>Итого в месяц:</b> {format_money(total_monthly)}\n"
            f"📅 <b>В год:</b> {format_money(total_yearly)}\n"
        )

        if cancelled:
            saved = sum(
                get_monthly_price(s.price, s.billing_cycle)
                for s in cancelled
            )
            text += (
                f"\n✂️ Отменено подписок: {len(cancelled)} "
                f"(экономия {format_money(saved)}/мес)"
            )

        # Кнопки для каждой подписки
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        builder = InlineKeyboardBuilder()
        for s in active[:10]:  # Лимит 10 кнопок
            monthly = get_monthly_price(s.price, s.billing_cycle)
            builder.row(
                InlineKeyboardButton(
                    text=f"{'🟢' if s.usage_level in ('high', 'medium') else '🔴'} {s.name} — {format_money(monthly)}/мес",
                    callback_data=f"view_sub_{s.id}",
                )
            )

        builder.row(
            InlineKeyboardButton(
                text="➕ Добавить подписку",
                callback_data="add_subscription",
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🔙 Главное меню",
                callback_data="back_to_menu",
            )
        )

        kb = builder.as_markup()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)


# ============== Просмотр подписки ==============

@router.callback_query(F.data.startswith("view_sub_"))
async def view_subscription(callback: CallbackQuery):
    """Детальный просмотр подписки."""
    sub_id = int(callback.data.split("_")[-1])
    user = await get_user_by_tg_id(callback.from_user.id)

    if not user:
        await callback.answer("❌ /start сначала", show_alert=True)
        return

    async with async_session() as session:
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
    yearly = monthly * 12
    category_name = SUBSCRIPTION_CATEGORIES.get(
        sub.category, "📦 Другое"
    )

    text = (
        f"📋 <b>{sub.name}</b>\n\n"
        f"💰 Цена: {format_money(sub.price)} "
        f"({billing_cycle_name(sub.billing_cycle)})\n"
        f"📅 В месяц: {format_money(monthly)}\n"
        f"📅 В год: {format_money(yearly)}\n"
        f"📁 Категория: {category_name}\n"
        f"📊 Статус: {sub.status}\n"
    )

    if sub.next_billing_date:
        d = days_until(sub.next_billing_date)
        text += (
            f"⏰ Следующее списание: "
            f"{sub.next_billing_date.strftime('%d.%m.%Y')} "
            f"(через {d} дн.)\n"
        )

    if sub.is_trial and sub.trial_end_date:
        td = days_until(sub.trial_end_date)
        text += (
            f"🆓 Trial до: "
            f"{sub.trial_end_date.strftime('%d.%m.%Y')} "
            f"({td} дн.)\n"
        )

    if sub.last_used:
        lu_days = (date.today() - sub.last_used).days
        text += f"📱 Последнее использование: {lu_days} дн. назад\n"

    if sub.notes:
        text += f"📝 Заметка: {sub.notes}\n"

    if sub.created_at:
        age = (datetime.utcnow() - sub.created_at).days
        text += f"📆 Отслеживается: {age} дн.\n"

    await callback.message.edit_text(
        text,
        reply_markup=subscription_actions_keyboard(
            sub_id, user.is_premium
        ),
    )
    await callback.answer()


# ============== Добавление подписки ==============

@router.callback_query(F.data == "add_subscription")
@router.message(Command("add"))
@router.message(F.text == "➕ Добавить")
async def start_add_subscription(
    event: Message | CallbackQuery,
):
    """Начало добавления подписки."""
    text = (
        "➕ <b>Добавить подписку</b>\n\n"
        "Выбери способ добавления:"
    )
    kb = add_subscription_keyboard()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, reply_markup=kb)


# --- Из списка ---

@router.callback_query(F.data == "add_from_list")
async def add_from_list(callback: CallbackQuery):
    """Выбор категории для добавления."""
    text = (
        "📁 <b>Выбери категорию</b>\n\n"
        "Я покажу популярные подписки:"
    )
    await callback.message.edit_text(
        text, reply_markup=categories_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cat_"))
async def show_category_subs(callback: CallbackQuery):
    """Подписки в выбранной категории."""
    category = callback.data.replace("cat_", "")
    category_name = SUBSCRIPTION_CATEGORIES.get(
        category, "Другое"
    )

    text = f"{category_name}\n\nВыбери подписку или введи свою:"
    await callback.message.edit_text(
        text, reply_markup=popular_subs_keyboard(category)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("quickadd_"))
async def quick_add_subscription(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Быстрое добавление из списка."""
    parts = callback.data.replace("quickadd_", "").rsplit("_", 1)
    name = parts[0]
    price = float(parts[1])

    # Находим категорию
    category = "other"
    for s in POPULAR_SUBSCRIPTIONS:
        if s["name"] == name:
            category = s["category"]
            break

    await state.update_data(
        name=name,
        price=price,
        category=category,
    )

    text = (
        f"⏱ <b>Как часто списывается {name}?</b>\n\n"
        f"Цена: {format_money(price)}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=billing_cycle_keyboard(name),
    )
    await state.set_state(AddSubStates.waiting_cycle)
    await callback.answer()


# --- Ввод вручную ---

@router.callback_query(F.data == "add_manual")
async def add_manual_start(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Начало ручного ввода подписки."""
    text = (
        "📝 <b>Ввод подписки вручную</b>\n\n"
        "Введи название сервиса:\n"
        "Например: Netflix, Spotify, Яндекс Плюс"
    )
    await callback.message.edit_text(text)
    await state.set_state(AddSubStates.waiting_name)
    await callback.answer()


@router.message(StateFilter(AddSubStates.waiting_name))
async def process_sub_name(message: Message, state: FSMContext):
    """Получение названия подписки."""
    name = message.text.strip()

    if len(name) > 100:
        await message.answer(
            "❌ Слишком длинное название. Попробуй короче."
        )
        return

    if len(name) < 2:
        await message.answer(
            "❌ Слишком короткое название. Минимум 2 символа."
        )
        return

    await state.update_data(name=name)

    # Проверяем, есть ли в популярных
    found = None
    for s in POPULAR_SUBSCRIPTIONS:
        if s["name"].lower() == name.lower():
            found = s
            break

    if found:
        await state.update_data(
            price=found["price"],
            category=found["category"],
        )
        await message.answer(
            f"✅ Нашёл <b>{found['name']}</b>!\n"
            f"Цена по умолчанию: {format_money(found['price'])}/мес\n\n"
            f"Введи свою цену или нажми кнопку, "
            f"чтобы оставить эту:",
        )
    else:
        await message.answer(
            f"✅ Подписка: <b>{name}</b>\n\n"
            f"Введи цену (в рублях):\n"
            f"Например: 499"
        )

    await state.set_state(AddSubStates.waiting_price)


@router.message(StateFilter(AddSubStates.waiting_price))
async def process_sub_price(message: Message, state: FSMContext):
    """Получение цены подписки."""
    try:
        price_text = message.text.strip().replace(",", ".").replace("₽", "").replace("руб", "").strip()
        price = float(price_text)
        if price <= 0 or price > 1_000_000:
            raise ValueError
    except ValueError:
        await message.answer(
            "❌ Введи корректную цену (число в рублях).\n"
            "Например: 499"
        )
        return

    data = await state.get_data()
    name = data.get("name", "")

    await state.update_data(price=price)

    await message.answer(
        f"💰 Цена: {format_money(price)}\n\n"
        f"⏱ Как часто списывается <b>{name}</b>?",
        reply_markup=billing_cycle_keyboard(name),
    )
    await state.set_state(AddSubStates.waiting_cycle)


@router.callback_query(
    F.data.startswith("cycle_"),
    StateFilter(AddSubStates.waiting_cycle),
)
async def process_billing_cycle(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Получение периода оплаты."""
    cycle = callback.data.replace("cycle_", "")
    await state.update_data(billing_cycle=cycle)

    data = await state.get_data()

    # Если категория ещё не выбрана
    if "category" not in data:
        await callback.message.edit_text(
            "📁 Выбери категорию подписки:",
            reply_markup=categories_keyboard(),
        )
        await state.set_state(AddSubStates.waiting_category)
    else:
        # Спрашиваем дату следующего списания
        await callback.message.edit_text(
            "📅 <b>Когда следующее списание?</b>\n\n"
            "Введи дату в формате ДД.ММ.ГГГГ\n"
            "Или напиши <b>пропустить</b>, чтобы "
            "я рассчитал автоматически."
        )
        await state.set_state(AddSubStates.waiting_next_billing)

    await callback.answer()


@router.callback_query(
    F.data.startswith("cat_"),
    StateFilter(AddSubStates.waiting_category),
)
async def process_category(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Получение категории при ручном добавлении."""
    category = callback.data.replace("cat_", "")
    await state.update_data(category=category)

    await callback.message.edit_text(
        "📅 <b>Когда следующее списание?</b>\n\n"
        "Введи дату в формате ДД.ММ.ГГГГ\n"
        "Или напиши <b>пропустить</b>."
    )
    await state.set_state(AddSubStates.waiting_next_billing)
    await callback.answer()


@router.message(StateFilter(AddSubStates.waiting_next_billing))
async def process_next_billing(
    message: Message,
    state: FSMContext,
):
    """Получение даты следующего списания."""
    text = message.text.strip().lower()

    next_billing = None
    if text in ("пропустить", "skip", "-", "нет"):
        data = await state.get_data()
        cycle = data.get("billing_cycle", BillingCycle.MONTHLY.value)
        next_billing = get_next_billing_date(date.today(), cycle)
    else:
        try:
            next_billing = datetime.strptime(
                text, "%d.%m.%Y"
            ).date()
        except ValueError:
            await message.answer(
                "❌ Неверный формат. Введи дату как ДД.ММ.ГГГГ\n"
                "Или напиши <b>пропустить</b>"
            )
            return

    await state.update_data(
        next_billing_date=next_billing.isoformat()
    )

    # Подтверждение
    data = await state.get_data()
    name = data["name"]
    price = data["price"]
    cycle = data.get("billing_cycle", "monthly")
    category = data.get("category", "other")
    category_name = SUBSCRIPTION_CATEGORIES.get(
        category, "📦 Другое"
    )
    monthly = get_monthly_price(price, cycle)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data="confirm_add_sub",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_add_sub",
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🆓 Это trial (пробный период)",
            callback_data="mark_as_trial",
        )
    )

    text = (
        f"📋 <b>Подтверди добавление:</b>\n\n"
        f"📌 Название: <b>{name}</b>\n"
        f"💰 Цена: {format_money(price)} "
        f"({billing_cycle_name(cycle)})\n"
        f"📅 В месяц: {format_money(monthly)}\n"
        f"📁 Категория: {category_name}\n"
        f"⏰ Следующее списание: "
        f"{next_billing.strftime('%d.%m.%Y')}\n"
    )

    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(AddSubStates.confirm)


@router.callback_query(
    F.data == "mark_as_trial",
    StateFilter(AddSubStates.confirm),
)
async def mark_as_trial(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Пометить как trial."""
    data = await state.get_data()
    await state.update_data(is_trial=True)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить (Trial)",
            callback_data="confirm_add_sub",
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data="cancel_add_sub",
        ),
    )

    name = data["name"]
    await callback.message.edit_text(
        callback.message.text + "\n🆓 <b>Помечена как Trial</b>",
        reply_markup=builder.as_markup(),
    )
    await callback.answer("Помечена как пробный период ✅")


@router.callback_query(
    F.data == "confirm_add_sub",
    StateFilter(AddSubStates.confirm),
)
async def confirm_add_sub(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Подтверждение добавления подписки."""
    data = await state.get_data()
    user = await get_user_by_tg_id(callback.from_user.id)

    if not user:
        await callback.answer("❌ /start", show_alert=True)
        await state.clear()
        return

    next_billing = None
    if data.get("next_billing_date"):
        next_billing = date.fromisoformat(
            data["next_billing_date"]
        )

    is_trial = data.get("is_trial", False)
    trial_end = next_billing if is_trial else None

    async with async_session() as session:
        sub = Subscription(
            user_id=user.id,
            name=data["name"],
            price=data["price"],
            category=data.get("category", "other"),
            billing_cycle=data.get(
                "billing_cycle", BillingCycle.MONTHLY.value
            ),
            next_billing_date=next_billing,
            is_trial=is_trial,
            trial_end_date=trial_end,
            status=(
                SubscriptionStatus.TRIAL.value
                if is_trial
                else SubscriptionStatus.ACTIVE.value
            ),
            usage_level=UsageLevel.UNKNOWN.value,
        )
        session.add(sub)

        # Обновляем дату последней новой подписки
        result = await session.execute(
            select(User).where(User.id == user.id)
        )
        db_user = result.scalar_one()
        db_user.last_new_sub_date = date.today()

        # Обновляем глобальную статистику
        stats_result = await session.execute(
            select(GlobalStats).limit(1)
        )
        stats = stats_result.scalar_one_or_none()
        if stats:
            stats.total_subscriptions_found += 1

        await session.commit()
        await session.refresh(sub)

        # Создаём уведомление о продлении
        if next_billing:
            reminder_date = datetime.combine(
                next_billing - timedelta(days=3),
                datetime.min.time().replace(hour=10),
            )
            if reminder_date > datetime.utcnow():
                notif = Notification(
                    user_id=user.id,
                    subscription_id=sub.id,
                    notification_type=NotificationType.RENEWAL_REMINDER.value,
                    message=(
                        f"⏰ Через 3 дня спишется "
                        f"{format_money(sub.price)} за {sub.name}!"
                    ),
                    scheduled_at=reminder_date,
                )
                session.add(notif)

            # Для trial — уведомление за 1 день
            if is_trial and trial_end:
                trial_reminder = datetime.combine(
                    trial_end - timedelta(days=1),
                    datetime.min.time().replace(hour=10),
                )
                if trial_reminder > datetime.utcnow():
                    trial_notif = Notification(
                        user_id=user.id,
                        subscription_id=sub.id,
                        notification_type=NotificationType.TRIAL_ENDING.value,
                        message=(
                            f"🆓 Trial {sub.name} заканчивается "
                            f"завтра! Продлить или отменить?"
                        ),
                        scheduled_at=trial_reminder,
                    )
                    session.add(trial_notif)

            await session.commit()

    monthly = get_monthly_price(
        data["price"],
        data.get("billing_cycle", "monthly"),
    )

    text = (
        f"✅ <b>Подписка добавлена!</b>\n\n"
        f"📌 {data['name']} — {format_money(monthly)}/мес\n\n"
    )

    if is_trial:
        text += (
            f"🆓 Trial активен. Я напомню тебе "
            f"за 1 день до окончания!\n\n"
        )

    text += (
        f"💡 Оцени, как часто ты используешь {data['name']}:\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=usage_level_keyboard(sub.id),
    )
    await state.clear()
    await callback.answer("✅ Подписка добавлена!")


@router.callback_query(
    F.data == "cancel_add_sub",
    StateFilter(AddSubStates.confirm),
)
async def cancel_add_sub(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Отмена добавления."""
    await state.clear()
    await callback.message.edit_text(
        "❌ Добавление отменено.",
        reply_markup=back_to_menu_keyboard(),
    )
    await callback.answer()


# ============== Оценка использования ==============

@router.callback_query(F.data.startswith("rate_usage_"))
async def start_rate_usage(callback: CallbackQuery):
    """Начало оценки использования."""
    sub_id = int(callback.data.replace("rate_usage_", ""))

    await callback.message.edit_text(
        "📊 <b>Как часто ты используешь эту подписку?</b>",
        reply_markup=usage_level_keyboard(sub_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("usage_"))
async def set_usage_level(callback: CallbackQuery):
    """Установка уровня использования."""
    parts = callback.data.split("_")
    sub_id = int(parts[1])
    level = parts[2]

    user = await get_user_by_tg_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ /start", show_alert=True)
        return

    async with async_session() as session:
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

        sub.usage_level = level
        if level in (UsageLevel.HIGH.value, UsageLevel.MEDIUM.value):
            sub.last_used = date.today()

        await session.commit()

    usage_names = {
        "high": "🟢 Активно использую",
        "medium": "🟡 Иногда использую",
        "low": "🔴 Редко использую",
        "none": "⚫ Не использую",
    }

    monthly = get_monthly_price(sub.price, sub.billing_cycle)

    text = f"✅ Оценка обновлена: {usage_names.get(level, level)}\n\n"

    if level in ("low", "none"):
        text += (
            f"⚠️ Ты тратишь {format_money(monthly)}/мес "
            f"на <b>{sub.name}</b>, "
            f"но почти не пользуешься!\n\n"
            f"За год это {format_money(monthly * 12)} впустую.\n\n"
            f"Хочешь отменить или найти альтернативу?"
        )

        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton

        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="❌ Отменить подписку",
                callback_data=f"cancel_sub_{sub_id}",
            ),
            InlineKeyboardButton(
                text="💣 Найти альтернативу",
                callback_data=f"find_alt_{sub_id}",
            ),
        )
        builder.row(
            InlineKeyboardButton(
                text="🔙 К подпискам",
                callback_data="my_subscriptions",
            )
        )

        await callback.message.edit_text(
            text, reply_markup=builder.as_markup()
        )
    else:
        text += "Отлично! Продолжай пользоваться 👍"
        await callback.message.edit_text(
            text, reply_markup=back_to_menu_keyboard()
        )

    await callback.answer()


# ============== Отмена подписки ==============

@router.callback_query(F.data.startswith("cancel_sub_"))
async def cancel_subscription_prompt(callback: CallbackQuery):
    """Запрос подтверждения отмены подписки."""
    sub_id = int(callback.data.replace("cancel_sub_", ""))
    user = await get_user_by_tg_id(callback.from_user.id)

    if not user:
        await callback.answer("❌ /start", show_alert=True)
        return

    async with async_session() as session:
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
    yearly = monthly * 12

    text = (
        f"❌ <b>Отменить {sub.name}?</b>\n\n"
        f"💰 Ты будешь экономить:\n"
        f"• {format_money(monthly)} в месяц\n"
        f"• {format_money(yearly)} в год\n\n"
        f"Ты уверен?"
    )

    await callback.message.edit_text(
        text,
        reply_markup=confirm_cancel_keyboard(sub_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_cancel_"))
async def confirm_cancel_subscription(callback: CallbackQuery):
    """Подтверждение отмены подписки."""
    sub_id = int(callback.data.replace("confirm_cancel_", ""))
    user = await get_user_by_tg_id(callback.from_user.id)

    if not user:
        await callback.answer("❌ /start", show_alert=True)
        return

    async with async_session() as session:
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

        # Отмечаем как отменённую
        sub.status = SubscriptionStatus.CANCELLED.value
        sub.cancelled_at = datetime.utcnow()

        # Обновляем статистику пользователя
        user_result = await session.execute(
            select(User).where(User.id == user.id)
        )
        db_user = user_result.scalar_one()
        db_user.total_saved += monthly
        db_user.total_cancelled += 1

        # Обновляем глобальную статистику
        stats_result = await session.execute(
            select(GlobalStats).limit(1)
        )
        stats = stats_result.scalar_one_or_none()
        if stats:
            stats.total_saved += monthly
            stats.total_subscriptions_cancelled += 1

        # Social proof
        social_event = SocialProofEvent(
            user_id=callback.from_user.id,
            username_masked=mask_username(
                callback.from_user.username
            ),
            event_type="cancelled",
            details=(
                f"отменил(а) {sub.name} и "
                f"экономит {format_money(monthly)}/мес"
            ),
            amount=monthly,
        )
        session.add(social_event)

        # Удаляем связанные уведомления
        notif_result = await session.execute(
            select(Notification).where(
                Notification.subscription_id == sub_id,
                Notification.sent == False,
            )
        )
        for notif in notif_result.scalars():
            await session.delete(notif)

        await session.commit()

    yearly_saved = monthly * 12

    text = (
        f"✅ <b>{sub.name} отменена!</b>\n\n"
        f"💰 Ты начинаешь экономить:\n"
        f"• {format_money(monthly)}/мес\n"
        f"• {format_money(yearly_saved)}/год\n\n"
        f"🏆 Всего сэкономлено: "
        f"{format_money(db_user.total_saved)}/мес\n\n"
        f"🎉 Так держать! Деньги лучше работают на тебя."
    )

    # Проверяем ачивки
    from bot.handlers.leaderboard import check_achievements
    new_achievements = await check_achievements(
        callback.from_user.id
    )
    if new_achievements:
        text += "\n\n🏅 <b>Новые ачивки:</b>\n"
        for ach in new_achievements:
            text += f"{ach['emoji']} {ach['name']}\n"

    await callback.message.edit_text(
        text, reply_markup=back_to_menu_keyboard()
    )
    await callback.answer("✅ Подписка отменена!")


# ============== Редактирование ==============

@router.callback_query(F.data.startswith("edit_sub_"))
async def edit_subscription(callback: CallbackQuery):
    """Меню редактирования подписки."""
    sub_id = int(callback.data.replace("edit_sub_", ""))
    user = await get_user_by_tg_id(callback.from_user.id)

    if not user:
        await callback.answer("❌ /start", show_alert=True)
        return

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="💰 Изменить цену",
            callback_data=f"editfield_{sub_id}_price",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📅 Изменить дату списания",
            callback_data=f"editfield_{sub_id}_date",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="⏱ Изменить период",
            callback_data=f"editfield_{sub_id}_cycle",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📝 Добавить заметку",
            callback_data=f"editfield_{sub_id}_note",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=f"view_sub_{sub_id}",
        )
    )

    await callback.message.edit_text(
        "✏️ <b>Что хочешь изменить?</b>",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("editfield_"))
async def edit_field_prompt(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Запрос нового значения поля."""
    parts = callback.data.split("_")
    sub_id = int(parts[1])
    field = parts[2]

    await state.update_data(
        edit_sub_id=sub_id, edit_field=field
    )

    prompts = {
        "price": "💰 Введи новую цену (в рублях):",
        "date": "📅 Введи новую дату списания (ДД.ММ.ГГГГ):",
        "cycle": "⏱ Выбери новый период:",
        "note": "📝 Введи заметку:",
    }

    if field == "cycle":
        await callback.message.edit_text(
            prompts[field],
            reply_markup=billing_cycle_keyboard(""),
        )
        await state.set_state(EditSubStates.waiting_field)
    else:
        await callback.message.edit_text(prompts[field])
        await state.set_state(EditSubStates.waiting_new_value)

    await callback.answer()


@router.callback_query(
    F.data.startswith("cycle_"),
    StateFilter(EditSubStates.waiting_field),
)
async def edit_cycle(
    callback: CallbackQuery,
    state: FSMContext,
):
    """Обновление периода оплаты."""
    cycle = callback.data.replace("cycle_", "")
    data = await state.get_data()
    sub_id = data["edit_sub_id"]
    user = await get_user_by_tg_id(callback.from_user.id)

    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.id == sub_id,
                Subscription.user_id == user.id,
            )
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.billing_cycle = cycle
            # Пересчитываем следующую дату
            sub.next_billing_date = get_next_billing_date(
                date.today(), cycle
            )
            await session.commit()

    await state.clear()
    await callback.message.edit_text(
        f"✅ Период обновлён: {billing_cycle_name(cycle)}",
        reply_markup=back_to_menu_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(EditSubStates.waiting_new_value))
async def process_edit_value(
    message: Message,
    state: FSMContext,
):
    """Обработка нового значения поля."""
    data = await state.get_data()
    sub_id = data["edit_sub_id"]
    field = data["edit_field"]
    user = await get_user_by_tg_id(message.from_user.id)

    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.id == sub_id,
                Subscription.user_id == user.id,
            )
        )
        sub = result.scalar_one_or_none()

        if not sub:
            await message.answer("❌ Подписка не найдена.")
            await state.clear()
            return

        if field == "price":
            try:
                new_price = float(
                    message.text.strip()
                    .replace(",", ".")
                    .replace("₽", "")
                    .strip()
                )
                if new_price <= 0:
                    raise ValueError
                sub.price = new_price
                msg = f"✅ Цена обновлена: {format_money(new_price)}"
            except ValueError:
                await message.answer("❌ Введи число.")
                return

        elif field == "date":
            try:
                new_date = datetime.strptime(
                    message.text.strip(), "%d.%m.%Y"
                ).date()
                sub.next_billing_date = new_date
                msg = (
                    f"✅ Дата обновлена: "
                    f"{new_date.strftime('%d.%m.%Y')}"
                )
            except ValueError:
                await message.answer("❌ Формат: ДД.ММ.ГГГГ")
                return

        elif field == "note":
            sub.notes = message.text.strip()[:500]
            msg = "✅ Заметка добавлена."

        else:
            msg = "✅ Обновлено."

        await session.commit()

    await state.clear()
    await message.answer(
        msg, reply_markup=back_to_menu_keyboard()
    )


# ============== Напоминание о продлении ==============

@router.callback_query(F.data.startswith("set_reminder_"))
async def set_reminder(callback: CallbackQuery):
    """Установка напоминания о продлении (Premium)."""
    sub_id = int(callback.data.replace("set_reminder_", ""))
    user = await get_user_by_tg_id(callback.from_user.id)

    if not user or not user.is_premium:
        await callback.answer(
            "⭐ Эта функция доступна в Premium",
            show_alert=True,
        )
        return

    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.id == sub_id,
                Subscription.user_id == user.id,
            )
        )
        sub = result.scalar_one_or_none()

        if not sub or not sub.next_billing_date:
            await callback.answer(
                "❌ Нет даты списания", show_alert=True
            )
            return

        # Создаём напоминания: за 3 дня, за 1 день, в день
        for days_before in [3, 1, 0]:
            reminder_date = datetime.combine(
                sub.next_billing_date - timedelta(days=days_before),
                datetime.min.time().replace(hour=10),
            )
            if reminder_date <= datetime.utcnow():
                continue

            # Проверяем, нет ли уже такого
            existing = await session.execute(
                select(Notification).where(
                    Notification.subscription_id == sub_id,
                    Notification.scheduled_at == reminder_date,
                    Notification.sent == False,
                )
            )
            if existing.scalar_one_or_none():
                continue

            day_word = {
                3: "через 3 дня",
                1: "завтра",
                0: "сегодня",
            }

            notif = Notification(
                user_id=user.id,
                subscription_id=sub_id,
                notification_type=NotificationType.RENEWAL_REMINDER.value,
                message=(
                    f"⏰ {sub.name}: списание {day_word[days_before]}! "
                    f"({format_money(sub.price)})"
                ),
                scheduled_at=reminder_date,
            )
            session.add(notif)

        await session.commit()

    await callback.answer(
        "🔔 Напоминания установлены!", show_alert=True
    )


# ============== Настройки ==============

@router.callback_query(F.data == "settings")
async def show_settings(callback: CallbackQuery):
    """Показать настройки."""
    user = await get_user_by_tg_id(callback.from_user.id)
    if not user:
        await callback.answer("❌ /start", show_alert=True)
        return

    from bot.keyboards.inline import settings_keyboard

    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"🔔 Уведомления: "
        f"{'ВКЛ' if user.notifications_enabled else 'ВЫКЛ'}\n"
        f"📊 Еженедельный отчёт: "
        f"{'ВКЛ' if user.weekly_report_enabled else 'ВЫКЛ'}\n"
        f"💰 Валюта: {user.currency}\n"
        f"🔥 Стрик: {user.current_streak} дн.\n"
        f"🏆 Макс. стрик: {user.max_streak} дн.\n"
    )

    await callback.message.edit_text(
        text,
        reply_markup=settings_keyboard(
            user.notifications_enabled,
            user.weekly_report_enabled,
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_notifications")
async def toggle_notifications(callback: CallbackQuery):
    """Переключение уведомлений."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == callback.from_user.id
            )
        )
        user = result.scalar_one_or_none()
        if user:
            user.notifications_enabled = not user.notifications_enabled
            await session.commit()

            status = "включены ✅" if user.notifications_enabled else "выключены ❌"
            await callback.answer(
                f"Уведомления {status}", show_alert=True
            )

            from bot.keyboards.inline import settings_keyboard
            text = (
                "⚙️ <b>Настройки</b>\n\n"
                f"🔔 Уведомления: "
                f"{'ВКЛ' if user.notifications_enabled else 'ВЫКЛ'}\n"
                f"📊 Еженедельный отчёт: "
                f"{'ВКЛ' if user.weekly_report_enabled else 'ВЫКЛ'}\n"
            )
            await callback.message.edit_text(
                text,
                reply_markup=settings_keyboard(
                    user.notifications_enabled,
                    user.weekly_report_enabled,
                ),
            )


@router.callback_query(F.data == "toggle_weekly_report")
async def toggle_weekly_report(callback: CallbackQuery):
    """Переключение еженедельного отчёта."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == callback.from_user.id
            )
        )
        user = result.scalar_one_or_none()
        if user:
            user.weekly_report_enabled = not user.weekly_report_enabled
            await session.commit()

            status = "включён ✅" if user.weekly_report_enabled else "выключен ❌"
            await callback.answer(
                f"Еженедельный отчёт {status}",
                show_alert=True,
            )

            from bot.keyboards.inline import settings_keyboard
            text = (
                "⚙️ <b>Настройки</b>\n\n"
                f"🔔 Уведомления: "
                f"{'ВКЛ' if user.notifications_enabled else 'ВЫКЛ'}\n"
                f"📊 Еженедельный отчёт: "
                f"{'ВКЛ' if user.weekly_report_enabled else 'ВЫКЛ'}\n"
            )
            await callback.message.edit_text(
                text,
                reply_markup=settings_keyboard(
                    user.notifications_enabled,
                    user.weekly_report_enabled,
                ),
            )