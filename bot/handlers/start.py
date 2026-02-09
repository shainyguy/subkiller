"""Стартовые хендлеры: /start, /help, /menu, регистрация."""

from datetime import datetime, date
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command, CommandObject
from sqlalchemy import select, func

from bot.loader import bot
from bot.database import (
    async_session, User, Subscription,
    GlobalStats, SubscriptionStatus,
)
from bot.keyboards.inline import main_menu_keyboard
from bot.keyboards.reply import main_reply_keyboard
from bot.utils.helpers import (
    generate_referral_code, format_money,
)
from bot.config import config

router = Router()


async def get_or_create_user(
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    referred_by_code: str | None = None,
) -> User:
    """Получить или создать пользователя."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user:
            # Обновляем стрик
            today = date.today()
            if user.last_visit:
                diff = (today - user.last_visit).days
                if diff == 1:
                    user.current_streak += 1
                    if user.current_streak > user.max_streak:
                        user.max_streak = user.current_streak
                elif diff > 1:
                    user.current_streak = 1
            else:
                user.current_streak = 1

            user.last_visit = today
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            await session.commit()
            await session.refresh(user)
            return user

        # Обработка реферала
        referred_by_id = None
        if referred_by_code:
            ref_result = await session.execute(
                select(User).where(
                    User.referral_code == referred_by_code
                )
            )
            referrer = ref_result.scalar_one_or_none()
            if referrer:
                referred_by_id = referrer.telegram_id

        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            referral_code=generate_referral_code(telegram_id),
            referred_by=referred_by_id,
            last_visit=date.today(),
            current_streak=1,
            max_streak=1,
        )
        session.add(user)

        # Обновляем глобальную статистику
        stats_result = await session.execute(
            select(GlobalStats).limit(1)
        )
        stats = stats_result.scalar_one_or_none()
        if stats:
            stats.total_users += 1
        else:
            stats = GlobalStats(total_users=1)
            session.add(stats)

        await session.commit()
        await session.refresh(user)

        # Награждаем реферера
        if referred_by_id:
            from bot.handlers.referral import process_referral
            await process_referral(referred_by_id, telegram_id)

        return user


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    """Обработка команды /start."""
    referred_by_code = None
    if command.args and command.args.startswith("ref_"):
        referred_by_code = command.args.replace("ref_", "sk_")

    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        referred_by_code=referred_by_code,
    )

    # Получаем общую статистику
    async with async_session() as session:
        stats_result = await session.execute(
            select(GlobalStats).limit(1)
        )
        stats = stats_result.scalar_one_or_none()
        total_saved_all = stats.total_saved if stats else 0

    welcome_text = (
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"Я <b>SubRadar</b> 🗡 — трекер твоих подписок.\n\n"
        f"Средний человек тратит <b>15 000 — 50 000₽ в год</b> "
        f"на подписки, которыми не пользуется.\n\n"
        f"Я помогу тебе:\n"
        f"• 🔍 Найти ВСЕ регулярные списания\n"
        f"• 💀 Увидеть, сколько денег утекает\n"
        f"• 🔮 Предсказать ненужные траты\n"
        f"• 💣 Найти бесплатные альтернативы\n"
        f"• 🏆 Соревноваться в экономии\n\n"
        f"💰 Наши пользователи уже сэкономили: "
        f"<b>{format_money(total_saved_all)}</b>\n\n"
        f"Начни с добавления подписок ⬇️"
    )

    if user.referred_by:
        welcome_text += (
            "\n\n🎁 Тебя пригласил друг! "
            "Добавь подписки и узнай, сколько ты переплачиваешь."
        )

    await message.answer(
        welcome_text,
        reply_markup=main_reply_keyboard(
            webapp_url=config.webapp.url
        ),
    )

    await message.answer(
        "📱 <b>Главное меню</b>\n\n"
        "Выбери действие:",
        reply_markup=main_menu_keyboard(
            is_premium=user.is_premium,
            webapp_url=config.webapp.url,
        ),
    )


@router.message(Command("menu"))
@router.message(F.text == "📋 Подписки")
async def cmd_menu(message: Message):
    """Показать главное меню."""
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    await message.answer(
        "📱 <b>Главное меню</b>\n\nВыбери действие:",
        reply_markup=main_menu_keyboard(
            is_premium=user.is_premium,
            webapp_url=config.webapp.url,
        ),
    )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(callback: CallbackQuery):
    """Возврат в главное меню."""
    user = await get_or_create_user(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )

    await callback.message.edit_text(
        "📱 <b>Главное меню</b>\n\nВыбери действие:",
        reply_markup=main_menu_keyboard(
            is_premium=user.is_premium,
            webapp_url=config.webapp.url,
        ),
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Помощь."""
    help_text = (
        "❓ <b>Как пользоваться SubKiller</b>\n\n"

        "<b>🆓 Бесплатно:</b>\n"
        "• Добавлять подписки вручную или из списка\n"
        "• Пересылать SMS/уведомления от банка\n"
        "• Видеть список всех подписок\n"
        "• Счётчик боли — сколько денег утекает\n"
        "• Рейтинг экономии\n"
        "• Базовый еженедельный отчёт\n"
        "• 3 ачивки\n\n"

        "<b>⭐ Premium (490₽/мес):</b>\n"
        "• 🔮 Предсказатель утечки денег\n"
        "• 🧬 ДНК-профиль подписчика\n"
        "• 💣 AI-калькулятор замен\n"
        "• 🤖 Автоснайпер Trial\n"
        "• 🔔 Напоминания о продлении\n"
        "• 📊 Детальный дашборд здоровья\n"
        "• 🎰 Инвестиционный калькулятор\n"
        "• Все ачивки и челленджи\n"
        "• Приоритетная поддержка\n\n"

        "<b>Команды:</b>\n"
        "/start — Перезапуск бота\n"
        "/menu — Главное меню\n"
        "/add — Добавить подписку\n"
        "/subs — Мои подписки\n"
        "/pain — Счётчик боли\n"
        "/report — Отчёт о подписках\n"
        "/top — Рейтинг экономии\n"
        "/ref — Реферальная ссылка\n"
        "/premium — Информация о Premium\n"
        "/help — Эта справка\n\n"

        "💡 Ты также можешь <b>пересылать мне</b> "
        "SMS или email-уведомления от банка — "
        "я автоматически найду подписки!"
    )
    await message.answer(help_text)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Статистика для админа."""
    if message.from_user.id != config.bot.admin_id:
        await message.answer("⛔ Только для администратора.")
        return

    async with async_session() as session:
        stats_result = await session.execute(
            select(GlobalStats).limit(1)
        )
        stats = stats_result.scalar_one_or_none()

        users_count = await session.execute(
            select(func.count(User.id))
        )
        total_users = users_count.scalar()

        premium_count = await session.execute(
            select(func.count(User.id)).where(
                User.is_premium == True
            )
        )
        total_premium = premium_count.scalar()

        subs_count = await session.execute(
            select(func.count(Subscription.id))
        )
        total_subs = subs_count.scalar()

        active_subs_count = await session.execute(
            select(func.count(Subscription.id)).where(
                Subscription.status == SubscriptionStatus.ACTIVE.value
            )
        )
        total_active = active_subs_count.scalar()

    text = (
        "📊 <b>Статистика SubRadar</b>\n\n"
        f"👥 Пользователей: <b>{total_users}</b>\n"
        f"⭐ Premium: <b>{total_premium}</b>\n"
        f"📋 Всего подписок: <b>{total_subs}</b>\n"
        f"✅ Активных: <b>{total_active}</b>\n"
        f"💰 Всего сэкономлено: "
        f"<b>{format_money(stats.total_saved if stats else 0)}</b>\n"
    )


    await message.answer(text)
