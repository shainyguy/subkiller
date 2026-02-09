"""Модели базы данных SubKiller."""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Date,
    ForeignKey, Text, BigInteger, Enum as SAEnum
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, relationship
)
import enum


class Base(DeclarativeBase):
    pass


class BillingCycle(str, enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    TRIAL = "trial"
    PAUSED = "paused"


class UsageLevel(str, enum.Enum):
    HIGH = "high"         # Активно используется
    MEDIUM = "medium"     # Редко
    LOW = "low"           # Почти не используется
    NONE = "none"         # Не используется вообще
    UNKNOWN = "unknown"   # Нет данных


class NotificationType(str, enum.Enum):
    RENEWAL_REMINDER = "renewal_reminder"        # За 3 дня до продления
    TRIAL_ENDING = "trial_ending"                # За 1 день до конца trial
    WEEKLY_REPORT = "weekly_report"              # Еженедельный отчёт
    UNUSED_ALERT = "unused_alert"                # Не используешь подписку
    PRICE_CHANGE = "price_change"                # Изменение цены
    ACHIEVEMENT = "achievement"                  # Новая ачивка
    PREDICTION = "prediction"                    # Предсказание утечки


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"


# ============== USERS ==============

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    first_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    last_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # Premium
    is_premium: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    premium_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    premium_trial_used: Mapped[bool] = mapped_column(
        Boolean, default=False
    )

    # Referral
    referral_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    referred_by: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )

    # Статистика
    total_saved: Mapped[float] = mapped_column(
        Float, default=0.0
    )
    total_cancelled: Mapped[int] = mapped_column(
        Integer, default=0
    )

    # Стрик
    last_visit: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )
    current_streak: Mapped[int] = mapped_column(
        Integer, default=0
    )
    max_streak: Mapped[int] = mapped_column(
        Integer, default=0
    )
    last_new_sub_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )

    # ДНК профиль
    subscriber_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )

    # Настройки
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    weekly_report_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="RUB"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Связи
    subscriptions: Mapped[List["Subscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    achievements: Mapped[List["UserAchievement"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    payments: Mapped[List["Payment"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# ============== SUBSCRIPTIONS ==============

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    category: Mapped[str] = mapped_column(
        String(50), default="other"
    )
    price: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="RUB"
    )

    # Биллинг
    billing_cycle: Mapped[str] = mapped_column(
        String(20), default=BillingCycle.MONTHLY.value
    )
    next_billing_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )
    last_billing_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )

    # Trial
    is_trial: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    trial_end_date: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )
    auto_cancel_trial: Mapped[bool] = mapped_column(
        Boolean, default=False
    )

    # Статус и использование
    status: Mapped[str] = mapped_column(
        String(20), default=SubscriptionStatus.ACTIVE.value
    )
    usage_level: Mapped[str] = mapped_column(
        String(20), default=UsageLevel.UNKNOWN.value
    )
    last_used: Mapped[Optional[date]] = mapped_column(
        Date, nullable=True
    )
    usage_hours_per_month: Mapped[float] = mapped_column(
        Float, default=0.0
    )

    # Мета
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    cancel_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    icon: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # Связи
    user: Mapped["User"] = relationship(
        back_populates="subscriptions"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )


# ============== ACHIEVEMENTS ==============

class UserAchievement(Base):
    __tablename__ = "user_achievements"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    achievement_key: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    achieved_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    user: Mapped["User"] = relationship(
        back_populates="achievements"
    )


# ============== PAYMENTS ==============

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    yookassa_payment_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    amount: Mapped[float] = mapped_column(
        Float, nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(10), default="RUB"
    )
    status: Mapped[str] = mapped_column(
        String(20), default=PaymentStatus.PENDING.value
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    user: Mapped["User"] = relationship(
        back_populates="payments"
    )


# ============== NOTIFICATIONS ==============

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    subscription_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("subscriptions.id"), nullable=True
    )
    notification_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )
    sent: Mapped[bool] = mapped_column(
        Boolean, default=False
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    user: Mapped["User"] = relationship(
        back_populates="notifications"
    )
    subscription: Mapped[Optional["Subscription"]] = relationship(
        back_populates="notifications"
    )


# ============== SOCIAL PROOF LOG ==============

class SocialProofEvent(Base):
    __tablename__ = "social_proof_events"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False
    )
    username_masked: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "saved", "found_subs", "cancelled"
    details: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    amount: Mapped[float] = mapped_column(
        Float, default=0.0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


# ============== GLOBAL STATS ==============

class GlobalStats(Base):
    __tablename__ = "global_stats"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    total_users: Mapped[int] = mapped_column(
        Integer, default=0
    )
    total_saved: Mapped[float] = mapped_column(
        Float, default=0.0
    )
    total_subscriptions_found: Mapped[int] = mapped_column(
        Integer, default=0
    )
    total_subscriptions_cancelled: Mapped[int] = mapped_column(
        Integer, default=0
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )