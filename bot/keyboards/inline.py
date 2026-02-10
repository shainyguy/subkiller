"""Инлайн-клавиатуры."""

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.config import config, SUBSCRIPTION_CATEGORIES, POPULAR_SUBSCRIPTIONS


def main_menu_keyboard(
    is_premium: bool = False,
    webapp_url: str = ""
) -> InlineKeyboardMarkup:
    """Главное меню."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📋 Мои подписки",
            callback_data="my_subscriptions"
        ),
        InlineKeyboardButton(
            text="➕ Добавить подписку",
            callback_data="add_subscription"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="💀 Счётчик потерь",
            callback_data="pain_counter"
        ),
        InlineKeyboardButton(
            text="📊 Отчёт",
            callback_data="health_dashboard"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🔮 Прогноз трат",
            callback_data="predictions"
        ),
        InlineKeyboardButton(
            text="🎰 Упущенная выгода",
            callback_data="investments"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🧬 Мой профиль",
            callback_data="dna_profile"
        ),
        InlineKeyboardButton(
            text="💣 Альтернативы",
            callback_data="alternatives"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="🏆 Рейтинг экономии",
            callback_data="leaderboard"
        ),
        InlineKeyboardButton(
            text="🤖 Пробные периоды",
            callback_data="trial_sniper"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="👥 Пригласить друга",
            callback_data="referral"
        ),
        InlineKeyboardButton(
            text="⚙️ Настройки",
            callback_data="settings"
        ),
    )

    if webapp_url:
        builder.row(
            InlineKeyboardButton(
                text="🌐 Открыть Mini App",
                web_app=WebAppInfo(url=webapp_url)
            )
        )

    if not is_premium:
        builder.row(
            InlineKeyboardButton(
                text="⭐ Premium — 490₽/мес",
                callback_data="premium_info"
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="⭐ Premium активен",
                callback_data="premium_status"
            )
        )

    return builder.as_markup()


def add_subscription_keyboard() -> InlineKeyboardMarkup:
    """Способ добавления подписки."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📝 Ввести вручную",
            callback_data="add_manual"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📋 Выбрать из списка",
            callback_data="add_from_list"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📩 Переслать SMS/email",
            callback_data="add_from_message"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_menu"
        )
    )

    return builder.as_markup()


def categories_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура категорий."""
    builder = InlineKeyboardBuilder()

    for key, name in SUBSCRIPTION_CATEGORIES.items():
        builder.button(
            text=name,
            callback_data=f"cat_{key}"
        )

    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="add_subscription"
        )
    )
    return builder.as_markup()


def popular_subs_keyboard(
    category: str
) -> InlineKeyboardMarkup:
    """Популярные подписки в категории."""
    builder = InlineKeyboardBuilder()

    filtered = [
        s for s in POPULAR_SUBSCRIPTIONS
        if s["category"] == category
    ]

    for sub in filtered:
        price = sub["price"]
        builder.button(
            text=f"{sub['name']} — {price}₽/мес",
            callback_data=f"quickadd_{sub['name']}_{price}"
        )

    builder.adjust(1)
    builder.row(
        InlineKeyboardButton(
            text="📝 Другая подписка",
            callback_data="add_manual"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 К категориям",
            callback_data="add_from_list"
        )
    )
    return builder.as_markup()


def billing_cycle_keyboard(
    sub_name: str
) -> InlineKeyboardMarkup:
    """Выбор периода оплаты."""
    builder = InlineKeyboardBuilder()

    cycles = [
        ("Еженедельно", "weekly"),
        ("Ежемесячно", "monthly"),
        ("Раз в 3 месяца", "quarterly"),
        ("Раз в полгода", "semi_annual"),
        ("Ежегодно", "annual"),
    ]

    for name, value in cycles:
        builder.button(
            text=name,
            callback_data=f"cycle_{value}"
        )

    builder.adjust(1)
    return builder.as_markup()


def usage_level_keyboard(
    sub_id: int
) -> InlineKeyboardMarkup:
    """Оценка использования подписки."""
    builder = InlineKeyboardBuilder()

    levels = [
        ("🟢 Активно использую", "high"),
        ("🟡 Иногда использую", "medium"),
        ("🔴 Почти не использую", "low"),
        ("⚫ Не использую вообще", "none"),
    ]

    for name, value in levels:
        builder.button(
            text=name,
            callback_data=f"usage_{sub_id}_{value}"
        )

    builder.adjust(1)
    return builder.as_markup()


def subscription_actions_keyboard(
    sub_id: int,
    is_premium: bool = False,
) -> InlineKeyboardMarkup:
    """Действия с подпиской."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="📊 Оценить использование",
            callback_data=f"rate_usage_{sub_id}"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"edit_sub_{sub_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отменить подписку",
            callback_data=f"cancel_sub_{sub_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(
            text="💣 Найти альтернативу",
            callback_data=f"find_alt_{sub_id}"
        )
    )

    if is_premium:
        builder.row(
            InlineKeyboardButton(
                text="🔔 Напоминание о продлении",
                callback_data=f"set_reminder_{sub_id}"
            )
        )

    builder.row(
        InlineKeyboardButton(
            text="🔙 К списку подписок",
            callback_data="my_subscriptions"
        )
    )

    return builder.as_markup()


def confirm_cancel_keyboard(
    sub_id: int
) -> InlineKeyboardMarkup:
    """Подтверждение отмены подписки."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Да, отменить",
            callback_data=f"confirm_cancel_{sub_id}"
        ),
        InlineKeyboardButton(
            text="❌ Нет, оставить",
            callback_data=f"view_sub_{sub_id}"
        ),
    )

    return builder.as_markup()


def premium_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура покупки Premium."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text=f"💳 Купить Premium — {config.premium.price}₽/мес",
            callback_data="buy_premium"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🎁 Попробовать 7 дней бесплатно",
            callback_data="try_premium_trial"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="👥 Получить бесплатно за друга",
            callback_data="referral"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_menu"
        )
    )

    return builder.as_markup()


def settings_keyboard(
    notifications: bool,
    weekly_report: bool,
) -> InlineKeyboardMarkup:
    """Настройки."""
    builder = InlineKeyboardBuilder()

    notif_text = "🔔 Уведомления: ВКЛ" if notifications else "🔕 Уведомления: ВЫКЛ"
    report_text = "📊 Еженедельный отчёт: ВКЛ" if weekly_report else "📊 Еженедельный отчёт: ВЫКЛ"

    builder.row(
        InlineKeyboardButton(
            text=notif_text,
            callback_data="toggle_notifications"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=report_text,
            callback_data="toggle_weekly_report"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data="back_to_menu"
        )
    )

    return builder.as_markup()


def back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """Кнопка назад к главному меню."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🔙 Главное меню",
            callback_data="back_to_menu"
        )
    )
    return builder.as_markup()


def pagination_keyboard(
    current_page: int,
    total_pages: int,
    prefix: str = "page"
) -> InlineKeyboardMarkup:
    """Пагинация."""
    builder = InlineKeyboardBuilder()

    buttons = []
    if current_page > 1:
        buttons.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"{prefix}_{current_page - 1}"
            )
        )

    buttons.append(
        InlineKeyboardButton(
            text=f"{current_page}/{total_pages}",
            callback_data="noop"
        )
    )

    if current_page < total_pages:
        buttons.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"{prefix}_{current_page + 1}"
            )
        )

    builder.row(*buttons)
    return builder.as_markup()

