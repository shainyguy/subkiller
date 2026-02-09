# 🗡 SubKiller Bot — Убийца забытых подписок

## Быстрый старт

### 1. Клонируй репозиторий
```bash
git clone <repo-url>
cd subkiller
```

### 2. Создай `.env` файл
```bash
cp .env.example .env
# Заполни все переменные
```

### 3. Получи токены

**Telegram Bot:**
- Создай бота через @BotFather
- Скопируй токен в `BOT_TOKEN`

**GigaChat:**
- Зарегистрируйся на https://developers.sber.ru
- Создай проект и получи Client ID/Secret
- Пропиши в `GIGACHAT_CLIENT_ID` и
  `GIGACHAT_CLIENT_SECRET`

**YooKassa:**
- Зарегистрируйся на https://yookassa.ru
- Создай магазин, получи Shop ID и Secret Key
- Пропиши в `YOOKASSA_SHOP_ID` и
  `YOOKASSA_SECRET_KEY`
- Настрой webhook: `https://your-app.railway.app/webhook/yookassa`
- События: `payment.succeeded`, `payment.canceled`

### 4. Локальный запуск
```bash
pip install -r requirements.txt
python -m bot.main
```

### 5. Деплой на Railway

#### Через CLI:
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

#### Через GitHub:
1. Запушь код на GitHub
2. Создай проект на https://railway.app
3. Подключи репозиторий
4. Добавь переменные окружения из `.env`
5. Деплой произойдёт автоматически

#### Переменные окружения Railway:
```
BOT_TOKEN=...
ADMIN_ID=...
GIGACHAT_CLIENT_ID=...
GIGACHAT_CLIENT_SECRET=...
YOOKASSA_SHOP_ID=...
YOOKASSA_SECRET_KEY=...
DATABASE_URL=sqlite+aiosqlite:///./subkiller.db
WEBAPP_URL=https://your-app.railway.app
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=$PORT
```

> **Важно:** Railway передаёт порт через `$PORT`.
> Убедись что `WEBAPP_PORT` = `$PORT`

### 6. Настрой Telegram Mini App
1. Открой @BotFather
2. `/mybots` → выбери бота → Bot Settings →
   Menu Button → Edit Menu Button
3. Укажи URL: `https://your-app.railway.app`
4. Текст кнопки: `🌐 Открыть Mini App`

### 7. Настрой YooKassa Webhook
1. В личном кабинете YooKassa
2. Настройки → HTTP-уведомления
3. URL: `https://your-app.railway.app/webhook/yookassa`
4. Включи: `payment.succeeded`, `payment.canceled`

## Архитектура

```
Bot (aiogram 3) ←→ SQLite DB ←→ FastAPI (Mini App)
       ↕                              ↕
   GigaChat AI                    YooKassa
       ↕                              ↕
   APScheduler                   Telegram WebApp
  (уведомления)                   (JS frontend)
```

## Бесплатные vs Premium функции

| Функция | Бесплатно | Premium |
|---------|-----------|---------|
| Добавление подписок | ✅ | ✅ |
| Парсинг SMS/email | ✅ | ✅ |
| Счётчик боли (базовый) | ✅ | ✅ |
| Рейтинг экономии | ✅ | ✅ |
| Еженедельный отчёт | ✅ | ✅ |
| 3 базовые ачивки | ✅ | ✅ |
| 🔮 Предсказатель утечки | ❌ | ✅ |
| 🧬 ДНК-профиль | ❌ | ✅ |
| 💣 AI-замены | ❌ | ✅ |
| 🤖 Автоснайпер Trial | ❌ | ✅ |
| 🔔 Умные напоминания | ❌ | ✅ |
| 🎰 Инвест. калькулятор | ❌ | ✅ |
| 17 ачивок | ❌ | ✅ |
| Mini App дашборд | ✅ | ✅ |