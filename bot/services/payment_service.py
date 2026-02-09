"""Сервис оплаты через YooKassa."""

import logging
import uuid
from datetime import datetime

from yookassa import Configuration, Payment as YooPayment
from sqlalchemy import select

from bot.config import config
from bot.database import (
    async_session, Payment, PaymentStatus,
)

logger = logging.getLogger(__name__)


class PaymentService:
    """Клиент YooKassa."""

    def __init__(self):
        Configuration.account_id = config.yookassa.shop_id
        Configuration.secret_key = config.yookassa.secret_key

    async def create_payment(
        self,
        amount: float,
        user_id: int,
        telegram_id: int,
        description: str = "SubKiller Premium",
    ) -> tuple[str, str]:
        """
        Создание платежа.
        Возвращает (payment_url, payment_id).
        """
        idempotence_key = str(uuid.uuid4())

        payment = YooPayment.create(
            {
                "amount": {
                    "value": str(amount),
                    "currency": "RUB",
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": (
                        f"{config.webapp.url}"
                        f"/payment/success"
                        f"?user_id={telegram_id}"
                    ),
                },
                "capture": True,
                "description": description,
                "metadata": {
                    "user_id": user_id,
                    "telegram_id": telegram_id,
                },
            },
            idempotence_key,
        )

        payment_url = payment.confirmation.confirmation_url
        payment_id = payment.id

        # Сохраняем в БД
        async with async_session() as session:
            db_payment = Payment(
                user_id=user_id,
                yookassa_payment_id=payment_id,
                amount=amount,
                currency="RUB",
                status=PaymentStatus.PENDING.value,
                description=description,
            )
            session.add(db_payment)
            await session.commit()

        logger.info(
            f"Payment created: {payment_id} "
            f"for user {telegram_id}"
        )
        return payment_url, payment_id

    async def check_payment(self, payment_id: str) -> bool:
        """Проверка статуса платежа."""
        try:
            payment = YooPayment.find_one(payment_id)
            return payment.status == "succeeded"
        except Exception as e:
            logger.error(f"Payment check error: {e}")
            return False

    async def cancel_payment(self, payment_id: str) -> bool:
        """Отмена платежа."""
        try:
            YooPayment.cancel(payment_id)
            return True
        except Exception as e:
            logger.error(f"Payment cancel error: {e}")
            return False


# Синглтон
payment_service = PaymentService()