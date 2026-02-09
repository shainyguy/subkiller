"""Генерация изображений для отчётов (шерабельные)."""

import io
import logging
from datetime import date
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Цвета
BG_COLOR = (18, 18, 30)
TEXT_WHITE = (255, 255, 255)
TEXT_GRAY = (150, 150, 170)
GREEN = (76, 217, 100)
YELLOW = (255, 204, 0)
RED = (255, 59, 48)
ORANGE = (255, 149, 0)
ACCENT = (94, 92, 230)
CARD_BG = (30, 30, 50)


def _get_font(size: int) -> ImageFont.FreeTypeFont:
    """Получить шрифт (с фоллбэком)."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def generate_health_report_image(
    username: str,
    total_monthly: float,
    green_subs: list[tuple[str, float]],
    yellow_subs: list[tuple[str, float]],
    red_subs: list[tuple[str, float]],
    health_score: int,
    potential_savings: float,
    date_str: Optional[str] = None,
) -> bytes:
    """Генерация красивого изображения дашборда."""
    width = 800
    height = 900

    # Рассчитываем динамическую высоту
    total_items = (
        len(green_subs) + len(yellow_subs) + len(red_subs)
    )
    height = max(900, 500 + total_items * 40)

    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_title = _get_font(28)
    font_large = _get_font(22)
    font_medium = _get_font(18)
    font_small = _get_font(14)

    y = 30

    # Заголовок
    draw.text(
        (30, y), "SUBKILLER", fill=ACCENT, font=font_title
    )
    y += 40
    if not date_str:
        date_str = date.today().strftime("%d.%m.%Y")
    draw.text(
        (30, y),
        f"Еженедельный отчёт — {date_str}",
        fill=TEXT_GRAY,
        font=font_small,
    )
    y += 35

    # Разделитель
    draw.line([(30, y), (width - 30, y)], fill=ACCENT, width=2)
    y += 20

    # Общий бюджет
    draw.text(
        (30, y),
        "Общий бюджет подписок:",
        fill=TEXT_GRAY,
        font=font_medium,
    )
    y += 28
    draw.text(
        (30, y),
        f"{total_monthly:,.0f} руб/мес".replace(",", " "),
        fill=TEXT_WHITE,
        font=font_large,
    )
    y += 40

    # Зелёные подписки
    if green_subs:
        draw.rectangle(
            [(25, y - 5), (width - 25, y + 25)],
            fill=(20, 60, 20),
        )
        draw.text(
            (35, y),
            f"Активно используешь ({len(green_subs)})",
            fill=GREEN,
            font=font_medium,
        )
        y += 35
        for name, price in green_subs:
            draw.text(
                (50, y),
                f"● {name}",
                fill=TEXT_WHITE,
                font=font_small,
            )
            price_text = f"{price:,.0f}₽".replace(",", " ")
            draw.text(
                (width - 120, y),
                price_text,
                fill=GREEN,
                font=font_small,
            )
            y += 28

    y += 10

    # Жёлтые
    if yellow_subs:
        draw.rectangle(
            [(25, y - 5), (width - 25, y + 25)],
            fill=(60, 50, 10),
        )
        draw.text(
            (35, y),
            f"Редко используешь ({len(yellow_subs)})",
            fill=YELLOW,
            font=font_medium,
        )
        y += 35
        for name, price in yellow_subs:
            draw.text(
                (50, y),
                f"● {name}",
                fill=TEXT_WHITE,
                font=font_small,
            )
            price_text = f"{price:,.0f}₽".replace(",", " ")
            draw.text(
                (width - 120, y),
                price_text,
                fill=YELLOW,
                font=font_small,
            )
            y += 28

    y += 10

    # Красные
    if red_subs:
        draw.rectangle(
            [(25, y - 5), (width - 25, y + 25)],
            fill=(60, 15, 15),
        )
        draw.text(
            (35, y),
            f"Не используешь ({len(red_subs)})",
            fill=RED,
            font=font_medium,
        )
        y += 35
        for name, price in red_subs:
            draw.text(
                (50, y),
                f"✕ {name}",
                fill=TEXT_WHITE,
                font=font_small,
            )
            price_text = f"{price:,.0f}₽".replace(",", " ")
            draw.text(
                (width - 120, y),
                price_text,
                fill=RED,
                font=font_small,
            )
            y += 28

    y += 20

    # Разделитель
    draw.line(
        [(30, y), (width - 30, y)], fill=ACCENT, width=1
    )
    y += 20

    # Оценка здоровья
    draw.text(
        (30, y),
        "Оценка здоровья:",
        fill=TEXT_GRAY,
        font=font_medium,
    )
    y += 30

    # Прогресс-бар
    bar_x = 30
    bar_width = width - 60
    bar_height = 25

    # Фон бара
    draw.rounded_rectangle(
        [(bar_x, y), (bar_x + bar_width, y + bar_height)],
        radius=12,
        fill=(50, 50, 70),
    )

    # Заполненная часть
    fill_width = int(bar_width * health_score / 100)
    if fill_width > 0:
        color = GREEN if health_score >= 60 else (
            YELLOW if health_score >= 40 else RED
        )
        draw.rounded_rectangle(
            [(bar_x, y), (bar_x + fill_width, y + bar_height)],
            radius=12,
            fill=color,
        )

    # Текст на баре
    score_text = f"{health_score}/100"
    draw.text(
        (bar_x + bar_width // 2 - 25, y + 3),
        score_text,
        fill=TEXT_WHITE,
        font=font_small,
    )
    y += bar_height + 20

    # Потенциальная экономия
    if potential_savings > 0:
        draw.rectangle(
            [(25, y), (width - 25, y + 60)],
            fill=CARD_BG,
        )
        draw.text(
            (35, y + 8),
            "Потенциальная экономия:",
            fill=TEXT_GRAY,
            font=font_medium,
        )
        savings_text = (
            f"{potential_savings:,.0f} руб/мес = "
            f"{potential_savings * 12:,.0f} руб/год"
        ).replace(",", " ")
        draw.text(
            (35, y + 33),
            savings_text,
            fill=GREEN,
            font=font_large,
        )
        y += 75

    # Подвал
    y += 10
    draw.text(
        (30, y),
        f"@{username} • SubKiller Bot",
        fill=TEXT_GRAY,
        font=font_small,
    )

    # Сохраняем
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", quality=95)
    buffer.seek(0)
    return buffer.getvalue()


def generate_pain_counter_image(
    username: str,
    today_wasted: float,
    month_wasted: float,
    year_wasted: float,
    lifetime_wasted: float,
    comparable: str,
    per_minute: float,
) -> bytes:
    """Генерация изображения счётчика боли."""
    width = 800
    height = 600

    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_title = _get_font(32)
    font_large = _get_font(28)
    font_medium = _get_font(20)
    font_small = _get_font(16)
    font_huge = _get_font(48)

    y = 30

    # Заголовок
    draw.text(
        (30, y), "💀 СЧЁТЧИК БОЛИ", fill=RED, font=font_title
    )
    y += 50

    draw.text(
        (30, y),
        "Пока ты читаешь это, у тебя утекло:",
        fill=TEXT_GRAY,
        font=font_medium,
    )
    y += 35
    draw.text(
        (30, y),
        f"{per_minute * 2:.2f} ₽",
        fill=RED,
        font=font_huge,
    )
    y += 65

    # Разделитель
    draw.line(
        [(30, y), (width - 30, y)], fill=RED, width=2
    )
    y += 25

    # Статистика
    stats = [
        ("Сегодня утекло:", today_wasted),
        ("В этом месяце:", month_wasted),
        ("С начала года:", year_wasted),
    ]

    for label, value in stats:
        draw.text(
            (30, y), label, fill=TEXT_GRAY, font=font_medium
        )
        val_text = f"{value:,.0f} ₽".replace(",", " ")
        draw.text(
            (width - 250, y),
            val_text,
            fill=RED,
            font=font_large,
        )
        y += 40

    y += 20

    # За жизнь
    draw.rectangle(
        [(25, y), (width - 25, y + 80)],
        fill=(60, 10, 10),
    )
    draw.text(
        (35, y + 10),
        "За всю жизнь ты потеряешь:",
        fill=TEXT_GRAY,
        font=font_medium,
    )
    lifetime_text = (
        f"{lifetime_wasted:,.0f} ₽".replace(",", " ")
    )
    draw.text(
        (35, y + 40),
        f"{lifetime_text} = {comparable}",
        fill=RED,
        font=font_large,
    )
    y += 100

    # Подвал
    draw.text(
        (30, y),
        f"@{username} • SubKiller Bot",
        fill=TEXT_GRAY,
        font=font_small,
    )

    buffer = io.BytesIO()
    img.save(buffer, format="PNG", quality=95)
    buffer.seek(0)
    return buffer.getvalue()