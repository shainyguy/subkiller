"""FastAPI Mini App — веб-интерфейс SubKiller."""

import logging
import json
import hashlib
import hmac
from datetime import datetime, date, timedelta
from typing import Optional
from urllib.parse import parse_qsl

from fastapi import (
    FastAPI, Request, HTTPException,
    Depends, Query,
)
from fastapi.responses import (
    HTMLResponse, JSONResponse, RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from sqlalchemy import select, desc, func

from bot.config import config
from bot.database import (
    async_session, init_db,
    User, Subscription, UserAchievement,
    GlobalStats, Payment, Notification,
    SubscriptionStatus, UsageLevel, PaymentStatus,
    NotificationType, BillingCycle,
)
from bot.utils.helpers import (
    format_money, get_monthly_price,
    get_health_score, health_emoji,
    calculate_investment_return,
    get_comparable_purchase, billing_cycle_name,
    get_next_billing_date, days_until,
)
from bot.config import (
    SUBSCRIPTION_CATEGORIES,
    POPULAR_SUBSCRIPTIONS,
    ACHIEVEMENTS,
    ALTERNATIVES_DB,
    SUBSCRIBER_TYPES,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SubKiller Mini App",
    version="1.0.0",
)

# Статика и шаблоны
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Создаём директории если нет
os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "images"), exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)
templates = Jinja2Templates(directory=TEMPLATES_DIR)


# ============== Модели запросов ==============

class AddSubscriptionRequest(BaseModel):
    name: str
    price: float
    category: str = "other"
    billing_cycle: str = "monthly"
    next_billing_date: Optional[str] = None
    is_trial: bool = False
    trial_end_date: Optional[str] = None


class UpdateSubscriptionRequest(BaseModel):
    price: Optional[float] = None
    usage_level: Optional[str] = None
    next_billing_date: Optional[str] = None
    notes: Optional[str] = None


class UpdateUsageRequest(BaseModel):
    usage_level: str


# ============== Валидация Telegram WebApp ==============

def validate_webapp_data(init_data: str) -> Optional[dict]:
    """Валидация данных от Telegram WebApp."""
    try:
        parsed = dict(parse_qsl(init_data))
        check_hash = parsed.pop("hash", "")

        data_check_arr = sorted(
            [f"{k}={v}" for k, v in parsed.items()]
        )
        data_check_string = "\n".join(data_check_arr)

        secret_key = hmac.new(
            b"WebAppData",
            config.bot.token.encode(),
            hashlib.sha256,
        ).digest()

        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        if computed_hash == check_hash:
            user_data = json.loads(parsed.get("user", "{}"))
            return user_data
        return None
    except Exception as e:
        logger.error(f"WebApp validation error: {e}")
        return None


async def get_user_from_tg_id(
    telegram_id: int,
) -> Optional[User]:
    """Получить пользователя по telegram_id."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.telegram_id == telegram_id
            )
        )
        return result.scalar_one_or_none()


# ============== Healthcheck ==============

@app.get("/health")
async def health_check():
    """Healthcheck для Railway."""
    return {"status": "ok", "service": "SubKiller"}


# ============== Страницы ==============

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Главная страница Mini App."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "webapp_url": config.webapp.url,
        },
    )


@app.get("/subscriptions", response_class=HTMLResponse)
async def subscriptions_page(request: Request):
    """Страница подписок."""
    return templates.TemplateResponse(
        "subscriptions.html",
        {"request": request},
    )


@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    """Страница аналитики."""
    return templates.TemplateResponse(
        "analytics.html",
        {"request": request},
    )


@app.get("/premium", response_class=HTMLResponse)
async def premium_page(request: Request):
    """Страница Premium."""
    return templates.TemplateResponse(
        "premium.html",
        {"request": request},
    )


# ============== API ==============

@app.get("/api/user/{telegram_id}")
async def api_get_user(telegram_id: int):
    """Получить данные пользователя."""
    user = await get_user_from_tg_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "username": user.username,
        "first_name": user.first_name,
        "is_premium": user.is_premium,
        "premium_until": (
            user.premium_until.isoformat()
            if user.premium_until else None
        ),
        "total_saved": user.total_saved,
        "total_cancelled": user.total_cancelled,
        "current_streak": user.current_streak,
        "subscriber_type": user.subscriber_type,
        "referral_code": user.referral_code,
    }


@app.get("/api/subscriptions/{telegram_id}")
async def api_get_subscriptions(telegram_id: int):
    """Получить подписки пользователя."""
    user = await get_user_from_tg_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    async with async_session() as session:
        result = await session.execute(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(desc(Subscription.price))
        )
        subs = list(result.scalars().all())

    subscriptions = []
    for s in subs:
        monthly = get_monthly_price(s.price, s.billing_cycle)
        subscriptions.append({
            "id": s.id,
            "name": s.name,
            "price": s.price,
            "monthly_price": monthly,
            "category": s.category,
            "category_name": SUBSCRIPTION_CATEGORIES.get(
                s.category, "Другое"
            ),
            "billing_cycle": s.billing_cycle,
            "billing_cycle_name": billing_cycle_name(
                s.billing_cycle
            ),
            "status": s.status,
            "usage_level": s.usage_level,
            "is_trial": s.is_trial,
            "trial_end_date": (
                s.trial_end_date.isoformat()
                if s.trial_end_date else None
            ),
            "next_billing_date": (
                s.next_billing_date.isoformat()
                if s.next_billing_date else None
            ),
            "days_until_billing": (
                days_until(s.next_billing_date)
                if s.next_billing_date else None
            ),
            "last_used": (
                s.last_used.isoformat()
                if s.last_used else None
            ),
            "notes": s.notes,
            "created_at": s.created_at.isoformat(),
        })

    return {"subscriptions": subscriptions}


@app.post("/api/subscriptions/{telegram_id}")
async def api_add_subscription(
    telegram_id: int,
    data: AddSubscriptionRequest,
):
    """Добавить подписку через Mini App."""
    user = await get_user_from_tg_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    next_billing = None
    if data.next_billing_date:
        next_billing = date.fromisoformat(
            data.next_billing_date
        )
    else:
        next_billing = get_next_billing_date(
            date.today(), data.billing_cycle
        )

    trial_end = None
    if data.is_trial and data.trial_end_date:
        trial_end = date.fromisoformat(data.trial_end_date)
    elif data.is_trial:
        trial_end = next_billing

    async with async_session() as session:
        sub = Subscription(
            user_id=user.id,
            name=data.name,
            price=data.price,
            category=data.category,
            billing_cycle=data.billing_cycle,
            next_billing_date=next_billing,
            is_trial=data.is_trial,
            trial_end_date=trial_end,
            status=(
                SubscriptionStatus.TRIAL.value
                if data.is_trial
                else SubscriptionStatus.ACTIVE.value
            ),
            usage_level=UsageLevel.UNKNOWN.value,
        )
        session.add(sub)

        # Уведомление
        if next_billing:
            reminder_date = datetime.combine(
                next_billing - timedelta(days=3),
                datetime.min.time().replace(hour=10),
            )
            if reminder_date > datetime.utcnow():
                notif = Notification(
                    user_id=user.id,
                    notification_type=(
                        NotificationType.RENEWAL_REMINDER.value
                    ),
                    message=(
                        f"⏰ Через 3 дня спишется "
                        f"{format_money(data.price)} "
                        f"за {data.name}!"
                    ),
                    scheduled_at=reminder_date,
                )
                session.add(notif)

        # Trial уведомление
        if data.is_trial and trial_end:
            trial_reminder = datetime.combine(
                trial_end - timedelta(days=1),
                datetime.min.time().replace(hour=10),
            )
            if trial_reminder > datetime.utcnow():
                trial_notif = Notification(
                    user_id=user.id,
                    notification_type=(
                        NotificationType.TRIAL_ENDING.value
                    ),
                    message=(
                        f"🆓 Trial {data.name} "
                        f"заканчивается завтра!"
                    ),
                    scheduled_at=trial_reminder,
                )
                session.add(trial_notif)

        # Обновляем дату последней подписки
        user_result = await session.execute(
            select(User).where(User.id == user.id)
        )
        db_user = user_result.scalar_one()
        db_user.last_new_sub_date = date.today()

        await session.commit()
        await session.refresh(sub)

    return {"status": "ok", "subscription_id": sub.id}


@app.put("/api/subscriptions/{telegram_id}/{sub_id}")
async def api_update_subscription(
    telegram_id: int,
    sub_id: int,
    data: UpdateSubscriptionRequest,
):
    """Обновить подписку."""
    user = await get_user_from_tg_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.id == sub_id,
                Subscription.user_id == user.id,
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise HTTPException(404, "Subscription not found")

        if data.price is not None:
            sub.price = data.price
        if data.usage_level is not None:
            sub.usage_level = data.usage_level
            if data.usage_level in ("high", "medium"):
                sub.last_used = date.today()
        if data.next_billing_date is not None:
            sub.next_billing_date = date.fromisoformat(
                data.next_billing_date
            )
        if data.notes is not None:
            sub.notes = data.notes

        await session.commit()

    return {"status": "ok"}


@app.delete("/api/subscriptions/{telegram_id}/{sub_id}")
async def api_cancel_subscription(
    telegram_id: int,
    sub_id: int,
):
    """Отменить подписку."""
    user = await get_user_from_tg_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.id == sub_id,
                Subscription.user_id == user.id,
            )
        )
        sub = result.scalar_one_or_none()
        if not sub:
            raise HTTPException(404, "Subscription not found")

        monthly = get_monthly_price(
            sub.price, sub.billing_cycle
        )

        sub.status = SubscriptionStatus.CANCELLED.value
        sub.cancelled_at = datetime.utcnow()

        # Обновляем статистику
        user_result = await session.execute(
            select(User).where(User.id == user.id)
        )
        db_user = user_result.scalar_one()
        db_user.total_saved += monthly
        db_user.total_cancelled += 1

        # Глобальная статистика
        stats_result = await session.execute(
            select(GlobalStats).limit(1)
        )
        stats = stats_result.scalar_one_or_none()
        if stats:
            stats.total_saved += monthly
            stats.total_subscriptions_cancelled += 1

        await session.commit()

    return {
        "status": "ok",
        "saved_monthly": monthly,
    }


@app.get("/api/analytics/{telegram_id}")
async def api_get_analytics(telegram_id: int):
    """Аналитика пользователя."""
    user = await get_user_from_tg_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    async with async_session() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id
            )
        )
        all_subs = list(result.scalars().all())

    active = [
        s for s in all_subs
        if s.status in (
            SubscriptionStatus.ACTIVE.value,
            SubscriptionStatus.TRIAL.value,
        )
    ]
    cancelled = [
        s for s in all_subs
        if s.status == SubscriptionStatus.CANCELLED.value
    ]

    total_monthly = sum(
        get_monthly_price(s.price, s.billing_cycle)
        for s in active
    )
    wasted_monthly = sum(
        get_monthly_price(s.price, s.billing_cycle)
        for s in active
        if s.usage_level in (
            UsageLevel.LOW.value, UsageLevel.NONE.value,
        )
    )
    saved_monthly = user.total_saved

    used_count = sum(
        1 for s in active
        if s.usage_level in (
            UsageLevel.HIGH.value, UsageLevel.MEDIUM.value,
        )
    )
    score = get_health_score(
        len(active), used_count,
        total_monthly, wasted_monthly,
    )

    # Категории
    categories = {}
    for s in active:
        m = get_monthly_price(s.price, s.billing_cycle)
        cat = SUBSCRIPTION_CATEGORIES.get(
            s.category, "Другое"
        )
        categories[cat] = categories.get(cat, 0) + m

    # Инвестиции
    invest_amount = max(wasted_monthly, total_monthly * 0.3)
    sp500_5y = calculate_investment_return(
        invest_amount, 5, 0.10
    )
    sp500_10y = calculate_investment_return(
        invest_amount, 10, 0.10
    )

    # Pain counter
    per_minute = wasted_monthly / 30 / 24 / 60
    now = datetime.now()
    minutes_today = now.hour * 60 + now.minute
    today_wasted = per_minute * minutes_today
    day_of_month = now.day
    month_wasted = (wasted_monthly / 30) * day_of_month

    return {
        "total_monthly": round(total_monthly, 0),
        "wasted_monthly": round(wasted_monthly, 0),
        "saved_monthly": round(saved_monthly, 0),
        "total_yearly": round(total_monthly * 12, 0),
        "wasted_yearly": round(wasted_monthly * 12, 0),
        "health_score": score,
        "health_emoji": health_emoji(score),
        "active_count": len(active),
        "cancelled_count": len(cancelled),
        "categories": categories,
        "investments": {
            "monthly_amount": round(invest_amount, 0),
            "sp500_5y": round(sp500_5y, 0),
            "sp500_10y": round(sp500_10y, 0),
        },
        "pain_counter": {
            "per_minute": round(per_minute, 4),
            "today": round(today_wasted, 0),
            "month": round(month_wasted, 0),
            "year": round(wasted_monthly * 12, 0),
        },
    }


@app.get("/api/achievements/{telegram_id}")
async def api_get_achievements(telegram_id: int):
    """Ачивки пользователя."""
    user = await get_user_from_tg_id(telegram_id)
    if not user:
        raise HTTPException(404, "User not found")

    async with async_session() as session:
        result = await session.execute(
            select(UserAchievement).where(
                UserAchievement.user_id == user.id
            )
        )
        user_achs = list(result.scalars().all())

    earned = []
    for ua in user_achs:
        ach = ACHIEVEMENTS.get(ua.achievement_key)
        if ach:
            earned.append({
                "key": ua.achievement_key,
                "name": ach["name"],
                "emoji": ach["emoji"],
                "description": ach["description"],
                "achieved_at": ua.achieved_at.isoformat(),
            })

    locked = []
    earned_keys = set(ua.achievement_key for ua in user_achs)
    for key, ach in ACHIEVEMENTS.items():
        if key not in earned_keys:
            locked.append({
                "key": key,
                "name": ach["name"],
                "emoji": ach["emoji"],
                "description": ach["description"],
            })

    return {"earned": earned, "locked": locked}


@app.get("/api/alternatives/{sub_name}")
async def api_get_alternatives(sub_name: str):
    """Альтернативы для подписки."""
    alts = ALTERNATIVES_DB.get(sub_name, [])

    # Поиск по частичному совпадению
    if not alts:
        for key in ALTERNATIVES_DB:
            if key.lower() in sub_name.lower():
                alts = ALTERNATIVES_DB[key]
                break
            if sub_name.lower() in key.lower():
                alts = ALTERNATIVES_DB[key]
                break

    return {"alternatives": alts}


@app.get("/api/popular-subscriptions")
async def api_popular_subscriptions():
    """Список популярных подписок."""
    return {
        "subscriptions": POPULAR_SUBSCRIPTIONS,
        "categories": SUBSCRIPTION_CATEGORIES,
    }


@app.get("/api/leaderboard")
async def api_leaderboard():
    """Лидерборд."""
    async with async_session() as session:
        result = await session.execute(
            select(User)
            .where(User.total_saved > 0)
            .order_by(desc(User.total_saved))
            .limit(20)
        )
        users = list(result.scalars().all())

        stats_result = await session.execute(
            select(GlobalStats).limit(1)
        )
        stats = stats_result.scalar_one_or_none()

    leaderboard = []
    for i, u in enumerate(users):
        name = u.username or u.first_name or "Аноним"
        if len(name) > 4:
            name = name[:4] + "***"
        leaderboard.append({
            "position": i + 1,
            "name": name,
            "saved": round(u.total_saved, 0),
            "cancelled": u.total_cancelled,
        })

    return {
        "leaderboard": leaderboard,
        "total_saved": round(
            stats.total_saved if stats else 0, 0
        ),
        "total_users": stats.total_users if stats else 0,
    }


# ============== YooKassa Webhook ==============

@app.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    """Обработка уведомлений от YooKassa."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    event_type = body.get("event")
    payment_obj = body.get("object", {})
    payment_id = payment_obj.get("id")
    status = payment_obj.get("status")

    logger.info(
        f"YooKassa webhook: {event_type}, "
        f"payment={payment_id}, status={status}"
    )

    if event_type == "payment.succeeded" and payment_id:
        async with async_session() as session:
            result = await session.execute(
                select(Payment).where(
                    Payment.yookassa_payment_id == payment_id
                )
            )
            payment = result.scalar_one_or_none()

            if payment and payment.status != PaymentStatus.SUCCEEDED.value:
                payment.status = PaymentStatus.SUCCEEDED.value
                payment.confirmed_at = datetime.utcnow()

                # Активируем Premium
                user_result = await session.execute(
                    select(User).where(
                        User.id == payment.user_id
                    )
                )
                user = user_result.scalar_one_or_none()

                if user:
                    now = datetime.utcnow()
                    if (
                        user.premium_until
                        and user.premium_until > now
                    ):
                        user.premium_until += timedelta(days=30)
                    else:
                        user.premium_until = now + timedelta(
                            days=30
                        )
                    user.is_premium = True

                    logger.info(
                        f"Premium activated for user "
                        f"{user.telegram_id} until "
                        f"{user.premium_until}"
                    )

                    # Уведомляем пользователя
                    try:
                        from bot.loader import bot
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=(
                                "🎉 <b>Оплата прошла!</b>\n\n"
                                "⭐ Premium активирован на "
                                "30 дней!\n"
                                f"📅 До: "
                                f"{user.premium_until.strftime('%d.%m.%Y')}"
                            ),
                        )
                    except Exception as e:
                        logger.error(
                            f"Notification error: {e}"
                        )

                await session.commit()

    elif event_type == "payment.canceled" and payment_id:
        async with async_session() as session:
            result = await session.execute(
                select(Payment).where(
                    Payment.yookassa_payment_id == payment_id
                )
            )
            payment = result.scalar_one_or_none()
            if payment:
                payment.status = PaymentStatus.CANCELLED.value
                await session.commit()

    return {"status": "ok"}


# ============== Payment Success Page ==============

@app.get("/payment/success", response_class=HTMLResponse)
async def payment_success(
    request: Request,
    user_id: int = Query(default=0),
):
    """Страница успешной оплаты."""
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">
        <title>Оплата успешна — SubKiller</title>
        <script src="https://telegram.org/js/telegram-web-app.js">
        </script>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont,
                    sans-serif;
                background: #12121e;
                color: #fff;
                display: flex;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                text-align: center;
                padding: 20px;
            }}
            .container {{
                max-width: 400px;
            }}
            .emoji {{ font-size: 64px; margin-bottom: 20px; }}
            h1 {{
                font-size: 24px;
                margin-bottom: 12px;
                color: #4cd964;
            }}
            p {{
                color: #9696a8;
                font-size: 16px;
                line-height: 1.5;
                margin-bottom: 24px;
            }}
            .btn {{
                display: inline-block;
                background: #5e5ce6;
                color: #fff;
                padding: 14px 32px;
                border-radius: 12px;
                text-decoration: none;
                font-size: 16px;
                font-weight: 600;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="emoji">🎉</div>
            <h1>Оплата прошла успешно!</h1>
            <p>
                Premium активирован на 30 дней.<br>
                Все функции теперь доступны.
            </p>
            <a href="#" class="btn"
               onclick="closeMiniApp()">
                Вернуться в бота
            </a>
        </div>
        <script>
            function closeMiniApp() {{
                if (window.Telegram &&
                    window.Telegram.WebApp) {{
                    Telegram.WebApp.close();
                }} else {{
                    window.close();
                }}
            }}
            // Автозакрытие через 5 секунд
            setTimeout(closeMiniApp, 5000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)