"""Конфигурация проекта SubKiller."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class BotConfig:
    token: str = ""
    admin_id: int = 0

    def __post_init__(self):
        self.token = os.getenv("BOT_TOKEN", "")
        self.admin_id = int(os.getenv("ADMIN_ID", "0"))


@dataclass
class GigaChatConfig:
    client_id: str = ""
    client_secret: str = ""
    auth_url: str = ""
    api_url: str = ""
    access_token: str = ""
    token_expires_at: float = 0.0

    def __post_init__(self):
        self.client_id = os.getenv("GIGACHAT_CLIENT_ID", "")
        self.client_secret = os.getenv("GIGACHAT_CLIENT_SECRET", "")
        self.auth_url = os.getenv(
            "GIGACHAT_AUTH_URL",
            "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        )
        self.api_url = os.getenv(
            "GIGACHAT_API_URL",
            "https://gigachat.devices.sberbank.ru/api/v1"
        )


@dataclass
class YooKassaConfig:
    shop_id: str = ""
    secret_key: str = ""

    def __post_init__(self):
        self.shop_id = os.getenv("YOOKASSA_SHOP_ID", "")
        self.secret_key = os.getenv("YOOKASSA_SECRET_KEY", "")


@dataclass
class DatabaseConfig:
    url: str = ""

    def __post_init__(self):
        self.url = os.getenv(
            "DATABASE_URL",
            "sqlite+aiosqlite:///./subkiller.db"
        )


@dataclass
class WebAppConfig:
    url: str = ""
    host: str = "0.0.0.0"
    port: int = 8080

    def __post_init__(self):
        self.url = os.getenv("WEBAPP_URL", "https://your-app.railway.app")
        self.host = os.getenv("WEBAPP_HOST", "0.0.0.0")
        
        # Railway ставит PORT автоматически
        port_str = os.getenv("PORT", "") or os.getenv("WEBAPP_PORT", "") or "8080"
        try:
            self.port = int(port_str)
        except (ValueError, TypeError):
            self.port = 8080


@dataclass
class PremiumConfig:
    price: int = 490
    trial_days: int = 7

    def __post_init__(self):
        self.price = int(os.getenv("PREMIUM_PRICE", "490"))
        self.trial_days = int(os.getenv("PREMIUM_TRIAL_DAYS", "7"))


# Категории подписок
SUBSCRIPTION_CATEGORIES: dict[str, str] = {
    "streaming": "🎬 Стриминг",
    "music": "🎵 Музыка",
    "cloud": "☁️ Облако и хранилища",
    "productivity": "📝 Продуктивность",
    "education": "📚 Образование",
    "fitness": "💪 Фитнес и здоровье",
    "gaming": "🎮 Игры",
    "news": "📰 Новости и медиа",
    "social": "📱 Соцсети",
    "vpn": "🔐 VPN и безопасность",
    "ai": "🤖 AI и нейросети",
    "design": "🎨 Дизайн",
    "development": "💻 Разработка",
    "finance": "💰 Финансы",
    "food": "🍕 Еда и доставка",
    "transport": "🚗 Транспорт",
    "dating": "❤️ Знакомства",
    "other": "📦 Другое",
}

# Предустановленные подписки (имя, категория, примерная цена)
POPULAR_SUBSCRIPTIONS: list[dict] = [
    {"name": "Netflix", "category": "streaming", "price": 1490},
    {"name": "Кинопоиск", "category": "streaming", "price": 599},
    {"name": "Иви", "category": "streaming", "price": 399},
    {"name": "Okko", "category": "streaming", "price": 399},
    {"name": "Wink", "category": "streaming", "price": 299},
    {"name": "START", "category": "streaming", "price": 399},
    {"name": "Spotify", "category": "music", "price": 199},
    {"name": "Яндекс Музыка", "category": "music", "price": 299},
    {"name": "Apple Music", "category": "music", "price": 199},
    {"name": "VK Музыка", "category": "music", "price": 199},
    {"name": "Яндекс Плюс", "category": "streaming", "price": 399},
    {"name": "Telegram Premium", "category": "social", "price": 399},
    {"name": "YouTube Premium", "category": "streaming", "price": 399},
    {"name": "ChatGPT Plus", "category": "ai", "price": 2050},
    {"name": "Midjourney", "category": "ai", "price": 1000},
    {"name": "Notion", "category": "productivity", "price": 800},
    {"name": "Adobe Creative Cloud", "category": "design", "price": 1500},
    {"name": "Figma", "category": "design", "price": 1200},
    {"name": "Canva Pro", "category": "design", "price": 999},
    {"name": "Headspace", "category": "fitness", "price": 499},
    {"name": "Duolingo Plus", "category": "education", "price": 699},
    {"name": "Skillbox", "category": "education", "price": 3490},
    {"name": "LinkedIn Premium", "category": "social", "price": 800},
    {"name": "Storytel", "category": "education", "price": 549},
    {"name": "Литрес Подписка", "category": "education", "price": 499},
    {"name": "iCloud+", "category": "cloud", "price": 99},
    {"name": "Google One", "category": "cloud", "price": 139},
    {"name": "Dropbox Plus", "category": "cloud", "price": 999},
    {"name": "NordVPN", "category": "vpn", "price": 399},
    {"name": "Xbox Game Pass", "category": "gaming", "price": 699},
    {"name": "PlayStation Plus", "category": "gaming", "price": 579},
    {"name": "Яндекс Доставка", "category": "food", "price": 199},
    {"name": "Самокат Плюс", "category": "food", "price": 199},
    {"name": "Тинькофф Про", "category": "finance", "price": 199},
]

# Типы подписчиков для ДНК-профиля
SUBSCRIBER_TYPES: dict[str, dict] = {
    "impulse_collector": {
        "name": "Импульсивный коллекционер",
        "emoji": "🎰",
        "description": (
            "Ты подписываешься на эмоциях, "
            "часто пробуешь новое, но быстро забываешь"
        ),
    },
    "trial_hunter": {
        "name": "Охотник за триалами",
        "emoji": "🎯",
        "description": (
            "Ты мастер бесплатных периодов, "
            "но иногда забываешь отписаться"
        ),
    },
    "loyal_payer": {
        "name": "Верный плательщик",
        "emoji": "💎",
        "description": (
            "Ты редко подписываешься, "
            "но никогда не отменяешь — даже когда не пользуешься"
        ),
    },
    "optimizer": {
        "name": "Оптимизатор",
        "emoji": "⚡",
        "description": (
            "Ты следишь за подписками и "
            "используешь большинство из них"
        ),
    },
    "digital_hoarder": {
        "name": "Цифровой барахольщик",
        "emoji": "📦",
        "description": (
            "У тебя подписки на все случаи жизни, "
            "многие дублируют друг друга"
        ),
    },
}

# Альтернативы подписок
ALTERNATIVES_DB: dict[str, list[dict]] = {
    "Adobe Creative Cloud": [
        {"name": "Photopea", "price": 0, "coverage": 85,
         "url": "https://photopea.com"},
        {"name": "GIMP", "price": 0, "coverage": 70,
         "url": "https://gimp.org"},
        {"name": "Pixlr", "price": 400, "coverage": 90,
         "url": "https://pixlr.com"},
    ],
    "Adobe Photoshop": [
        {"name": "Photopea", "price": 0, "coverage": 85,
         "url": "https://photopea.com"},
        {"name": "GIMP", "price": 0, "coverage": 70,
         "url": "https://gimp.org"},
    ],
    "Notion": [
        {"name": "Obsidian", "price": 0, "coverage": 80,
         "url": "https://obsidian.md"},
        {"name": "Logseq", "price": 0, "coverage": 60,
         "url": "https://logseq.com"},
        {"name": "Anytype", "price": 0, "coverage": 75,
         "url": "https://anytype.io"},
    ],
    "Netflix": [
        {"name": "Кинопоиск (Яндекс Плюс)", "price": 399,
         "coverage": 70, "url": "https://kinopoisk.ru"},
        {"name": "Иви", "price": 399, "coverage": 65,
         "url": "https://ivi.ru"},
    ],
    "Canva Pro": [
        {"name": "Canva Free", "price": 0, "coverage": 60,
         "url": "https://canva.com"},
        {"name": "Figma Free", "price": 0, "coverage": 50,
         "url": "https://figma.com"},
    ],
    "Spotify": [
        {"name": "Яндекс Музыка", "price": 0, "coverage": 80,
         "url": "https://music.yandex.ru"},
        {"name": "VK Музыка", "price": 0, "coverage": 75,
         "url": "https://vk.com/music"},
    ],
    "LinkedIn Premium": [
        {"name": "LinkedIn Free", "price": 0, "coverage": 60,
         "url": "https://linkedin.com"},
        {"name": "HH.ru", "price": 0, "coverage": 50,
         "url": "https://hh.ru"},
    ],
    "Headspace": [
        {"name": "Insight Timer", "price": 0, "coverage": 70,
         "url": "https://insighttimer.com"},
        {"name": "YouTube медитации", "price": 0, "coverage": 50,
         "url": "https://youtube.com"},
    ],
    "ChatGPT Plus": [
        {"name": "GigaChat", "price": 0, "coverage": 60,
         "url": "https://gigachat.ru"},
        {"name": "Claude Free", "price": 0, "coverage": 55,
         "url": "https://claude.ai"},
    ],
    "Midjourney": [
        {"name": "Kandinsky", "price": 0, "coverage": 50,
         "url": "https://fusionbrain.ai"},
        {"name": "Leonardo.ai Free", "price": 0, "coverage": 55,
         "url": "https://leonardo.ai"},
    ],
    "Dropbox Plus": [
        {"name": "Google Drive 15GB", "price": 0, "coverage": 60,
         "url": "https://drive.google.com"},
        {"name": "Яндекс Диск", "price": 0, "coverage": 55,
         "url": "https://disk.yandex.ru"},
    ],
    "Figma": [
        {"name": "Figma Free", "price": 0, "coverage": 70,
         "url": "https://figma.com"},
        {"name": "Penpot", "price": 0, "coverage": 50,
         "url": "https://penpot.app"},
    ],
    "NordVPN": [
        {"name": "ProtonVPN Free", "price": 0, "coverage": 50,
         "url": "https://protonvpn.com"},
        {"name": "Windscribe Free", "price": 0, "coverage": 45,
         "url": "https://windscribe.com"},
    ],
    "Duolingo Plus": [
        {"name": "Duolingo Free", "price": 0, "coverage": 70,
         "url": "https://duolingo.com"},
        {"name": "LingQ Free", "price": 0, "coverage": 40,
         "url": "https://lingq.com"},
    ],
    "Storytel": [
        {"name": "Литрес (бесплатные книги)", "price": 0,
         "coverage": 30, "url": "https://litres.ru"},
        {"name": "Аудиокниги ВК", "price": 0, "coverage": 40,
         "url": "https://vk.com"},
    ],
}

# Ачивки
ACHIEVEMENTS: dict[str, dict] = {
    "first_sub_added": {
        "name": "Первый шаг",
        "emoji": "👣",
        "description": "Добавил первую подписку",
    },
    "first_sub_cancelled": {
        "name": "Первая кровь",
        "emoji": "🗡",
        "description": "Отключил первую подписку",
    },
    "saved_1000": {
        "name": "Тысячник",
        "emoji": "💰",
        "description": "Сэкономил 1 000₽",
    },
    "saved_5000": {
        "name": "Экономист",
        "emoji": "💎",
        "description": "Сэкономил 5 000₽",
    },
    "saved_10000": {
        "name": "Финансовый ниндзя",
        "emoji": "🥷",
        "description": "Сэкономил 10 000₽",
    },
    "saved_50000": {
        "name": "Волк с Уолл-стрит",
        "emoji": "🐺",
        "description": "Сэкономил 50 000₽",
    },
    "saved_100000": {
        "name": "Легенда экономии",
        "emoji": "👑",
        "description": "Сэкономил 100 000₽",
    },
    "week_streak": {
        "name": "7 дней контроля",
        "emoji": "🔥",
        "description": "7 дней подряд заходишь в бота",
    },
    "month_streak": {
        "name": "Месяц дисциплины",
        "emoji": "⚡",
        "description": "30 дней подряд заходишь в бота",
    },
    "no_new_subs_week": {
        "name": "Стальная воля",
        "emoji": "🛡",
        "description": "Неделя без новых подписок",
    },
    "no_new_subs_month": {
        "name": "Несокрушимый",
        "emoji": "🏰",
        "description": "Месяц без новых подписок",
    },
    "five_subs_cancelled": {
        "name": "Серийный отменщик",
        "emoji": "✂️",
        "description": "Отключил 5 подписок",
    },
    "ten_subs_cancelled": {
        "name": "Машина разрушения",
        "emoji": "💀",
        "description": "Отключил 10 подписок",
    },
    "invited_friend": {
        "name": "Спаситель друга",
        "emoji": "🤝",
        "description": "Пригласил первого друга",
    },
    "invited_five": {
        "name": "Евангелист",
        "emoji": "📢",
        "description": "Пригласил 5 друзей",
    },
    "health_score_80": {
        "name": "Здоровые финансы",
        "emoji": "💚",
        "description": "Достиг 80+ баллов подписочного здоровья",
    },
    "health_score_100": {
        "name": "Абсолютное здоровье",
        "emoji": "🌟",
        "description": "Достиг 100 баллов подписочного здоровья",
    },
}


@dataclass
class Config:
    bot: BotConfig = field(default_factory=BotConfig)
    gigachat: GigaChatConfig = field(default_factory=GigaChatConfig)
    yookassa: YooKassaConfig = field(default_factory=YooKassaConfig)
    db: DatabaseConfig = field(default_factory=DatabaseConfig)
    webapp: WebAppConfig = field(default_factory=WebAppConfig)
    premium: PremiumConfig = field(default_factory=PremiumConfig)



config = Config()
