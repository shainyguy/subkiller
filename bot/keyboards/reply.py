"""Reply-клавиатуры."""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
)


def main_reply_keyboard(
    webapp_url: str = ""
) -> ReplyKeyboardMarkup:
    """Основная reply-клавиатура."""
    buttons = [
        [
            KeyboardButton(text="📋 Подписки"),
            KeyboardButton(text="💀 Счётчик потерь"),
        ],
        [
            KeyboardButton(text="➕ Добавить"),
            KeyboardButton(text="📊 Отчёт"),
        ],
        [
            KeyboardButton(text="🏆 Рейтинг"),
            KeyboardButton(text="⭐ Premium"),
        ],
    ]

    if webapp_url:
        buttons.append([
            KeyboardButton(
                text="🌐 Mini App",
                web_app=WebAppInfo(url=webapp_url)
            )
        ])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        is_persistent=True,

    )
