"""Сервис для работы с GigaChat API."""

import time
import ssl
import json
import logging
import uuid
from typing import Optional

import httpx
import certifi

from bot.config import config

logger = logging.getLogger(__name__)


class GigaChatService:
    """Клиент GigaChat API."""

    def __init__(self):
        self.cfg = config.gigachat
        self.access_token: str = ""
        self.token_expires_at: float = 0.0

    async def _get_token(self) -> str:
        """Получение или обновление access token."""
        if (
            self.access_token
            and time.time() < self.token_expires_at - 60
        ):
            return self.access_token

        logger.info("Получение нового токена GigaChat...")

        # Формируем credentials
        import base64
        credentials = base64.b64encode(
            f"{self.cfg.client_id}:{self.cfg.client_secret}".encode()
        ).decode()

        ssl_context = ssl.create_default_context(
            cafile=certifi.where()
        )
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with httpx.AsyncClient(
            verify=False, timeout=30.0
        ) as client:
            response = await client.post(
                self.cfg.auth_url,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "RqUID": str(uuid.uuid4()),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"scope": "GIGACHAT_API_PERS"},
            )
            response.raise_for_status()
            data = response.json()

        self.access_token = data["access_token"]
        self.token_expires_at = data.get(
            "expires_at", time.time() + 1800
        ) / 1000  # из миллисекунд

        logger.info("Токен GigaChat получен успешно")
        return self.access_token

    async def chat(
        self,
        user_message: str,
        system_prompt: str = "",
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> str:
        """Отправка сообщения в GigaChat."""
        token = await self._get_token()

        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })
        messages.append({
            "role": "user",
            "content": user_message,
        })

        payload = {
            "model": "GigaChat",
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(
            verify=False, timeout=60.0
        ) as client:
            response = await client.post(
                f"{self.cfg.api_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        return content.strip()

    async def parse_subscription_from_text(
        self, text: str
    ) -> list[dict]:
        """
        Парсинг подписок из текста SMS/email.
        Возвращает список найденных подписок.
        """
        system_prompt = """Ты — AI-ассистент для анализа финансовых уведомлений.
Твоя задача: найти в тексте информацию о подписках и регулярных списаниях.

Верни JSON-массив найденных подписок. Каждый элемент:
{
  "name": "Название сервиса",
  "price": числовая сумма в рублях,
  "billing_cycle": "weekly"|"monthly"|"quarterly"|"semi_annual"|"annual",
  "category": "streaming"|"music"|"cloud"|"productivity"|"education"|"fitness"|"gaming"|"news"|"social"|"vpn"|"ai"|"design"|"development"|"finance"|"food"|"transport"|"dating"|"other",
  "is_trial": true|false,
  "confidence": 0.0-1.0
}

Если подписок не найдено, верни пустой массив: []
Верни ТОЛЬКО JSON, без пояснений и markdown."""

        try:
            response = await self.chat(
                user_message=f"Проанализируй этот текст и найди подписки:\n\n{text}",
                system_prompt=system_prompt,
                temperature=0.1,
            )

            # Очищаем ответ от возможного markdown
            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])

            result = json.loads(cleaned)
            if isinstance(result, list):
                return result
            return []

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Ошибка парсинга GigaChat: {e}")
            return []

    async def analyze_usage_prediction(
        self,
        sub_name: str,
        days_since_signup: int,
        days_since_last_use: int,
        monthly_price: float,
    ) -> dict:
        """Предсказание: будет ли пользователь использовать подписку."""
        system_prompt = """Ты — AI-аналитик подписок.
Проанализируй данные и предскажи, будет ли пользователь использовать подписку.

Верни JSON:
{
  "will_abandon": true|false,
  "probability_percent": 0-100,
  "predicted_waste_6months": число в рублях,
  "recommendation": "краткая рекомендация",
  "reason": "объяснение предсказания"
}

Верни ТОЛЬКО JSON."""

        user_msg = (
            f"Подписка: {sub_name}\n"
            f"Подписан: {days_since_signup} дней назад\n"
            f"Последнее использование: "
            f"{days_since_last_use} дней назад\n"
            f"Цена: {monthly_price}₽/мес"
        )

        try:
            response = await self.chat(
                user_message=user_msg,
                system_prompt=system_prompt,
                temperature=0.2,
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])

            return json.loads(cleaned)

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Ошибка предсказания: {e}")
            return {
                "will_abandon": days_since_last_use > 30,
                "probability_percent": min(
                    95, days_since_last_use * 2
                ),
                "predicted_waste_6months": monthly_price * 6,
                "recommendation": "Рекомендуем оценить использование",
                "reason": "Нет данных для точного анализа",
            }

    async def get_subscriber_dna(
        self,
        total_subs: int,
        active_subs: int,
        cancelled_subs: int,
        trial_subs: int,
        avg_sub_age_days: float,
        total_monthly_spend: float,
        usage_pattern: str,
    ) -> dict:
        """Генерация ДНК-профиля подписчика."""
        system_prompt = """Ты — поведенческий аналитик подписок.
На основе данных определи тип подписчика.

Типы:
- impulse_collector: Подписывается импульсивно, много подписок
- trial_hunter: Охотится за бесплатными периодами
- loyal_payer: Редко подписывается, но никогда не отменяет
- optimizer: Следит за подписками, использует большинство
- digital_hoarder: Много подписок, которые дублируют друг друга

Верни JSON:
{
  "type": "тип из списка выше",
  "description": "описание на русском, 2-3 предложения, обращайся на ты",
  "risk_zones": ["список рисков"],
  "tip": "один конкретный совет"
}

Верни ТОЛЬКО JSON."""

        user_msg = (
            f"Всего подписок: {total_subs}\n"
            f"Активных: {active_subs}\n"
            f"Отменённых: {cancelled_subs}\n"
            f"Триальных: {trial_subs}\n"
            f"Средний возраст подписки: {avg_sub_age_days:.0f} дней\n"
            f"Трата в месяц: {total_monthly_spend}₽\n"
            f"Паттерн использования: {usage_pattern}"
        )

        try:
            response = await self.chat(
                user_message=user_msg,
                system_prompt=system_prompt,
                temperature=0.4,
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])

            return json.loads(cleaned)

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Ошибка ДНК-профиля: {e}")
            return {
                "type": "impulse_collector",
                "description": (
                    "Ты подписываешься на эмоциях "
                    "и часто забываешь отменить."
                ),
                "risk_zones": ["Бесплатные пробные периоды"],
                "tip": "Поставь напоминания об окончании триалов.",
            }

    async def find_alternatives(
        self,
        service_name: str,
        price: float,
        category: str,
    ) -> list[dict]:
        """Поиск альтернатив подписке через AI."""
        system_prompt = """Ты — эксперт по сервисам и приложениям.
Найди бесплатные или более дешёвые альтернативы указанному сервису.

Верни JSON-массив:
[
  {
    "name": "Название альтернативы",
    "price": цена в рублях (0 если бесплатно),
    "coverage": процент покрытия функционала (0-100),
    "url": "ссылка на сервис",
    "note": "краткое пояснение"
  }
]

Максимум 5 альтернатив. Сортируй по убыванию coverage.
Верни ТОЛЬКО JSON."""

        user_msg = (
            f"Сервис: {service_name}\n"
            f"Цена: {price}₽/мес\n"
            f"Категория: {category}\n"
            f"Найди бесплатные или дешёвые альтернативы."
        )

        try:
            response = await self.chat(
                user_message=user_msg,
                system_prompt=system_prompt,
                temperature=0.3,
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])

            result = json.loads(cleaned)
            if isinstance(result, list):
                return result[:5]
            return []

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Ошибка поиска альтернатив: {e}")
            return []


# Синглтон
gigachat_service = GigaChatService()