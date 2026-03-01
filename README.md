# Rent Telegram Mini App

Telegram-бот и Mini App для поиска недвижимости в аренду. Система объединяет парсер объявлений из Telegram-каналов, интерактивное Mini App и панель администратора.

## 🚀 Основные возможности

-   **Поиск и Фильтрация**: Удобный интерфейс Mini App для поиска жилья по 29+ городам, цене и ключевым словам.
-   **Автоматизированный Парсинг**: Сбор объявлений из популярных каналов с использованием Telethon.
-   **Уведомления**: Ежедневные рассылки новых подходящих объявлений пользователям.
-   **Админ-панель**: Управление источниками (каналами), модерация предложений и статистика.
-   **Миграции БД**: Управление схемой данных через Alembic.

## � Структура проекта

```bash
├── alembic/             # Миграции базы данных
├── app/
│   ├── api.py           # FastAPI сервер и lifespan события
│   ├── auth.py          # Аутентификация Telegram (initData)
│   ├── bot.py           # Telegram бот (aiogram 3)
│   ├── database.py      # Настройка SQLAlchemy и Upsert логика
│   ├── main.py          # Точка входа (Бот + API + Планировщик)
│   ├── models.py        # Модели данных (User, Listing, Channel и др.)
│   ├── parser.py        # Парсер на Telethon
│   ├── scheduler.py     # APScheduler (задачи очистки и парсинга)
│   └── routers/         # Эндпоинты: /client и /admin
├── web_app/             # Фронтенд (Vanilla JS, CSS, HTML)
├── alembic.ini          # Конфигурация Alembic
├── requirements.txt     # Фиксированные версии зависимостей
└── railway.toml         # Конфигурация для Railway (Docker, Healthcheck)
```

## ⚙️ Настройка и Установка

### 1. Подготовка
```bash
git clone <repository_url>
cd rent_web_v2
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Переменные окружения (.env)
| Переменная | Описание |
| :--- | :--- |
| `BOT_TOKEN` | Токен из BotFather |
| `ADMIN_ID` | Ваш Telegram ID для доступа к админке |
| `TELETHON_SESSION` | Строка сессии Telethon |
| `DATABASE_URL` | URL базы данных (SQLite по умолчанию) |
| `REDIS_URL` | (Опционально) Для хранения состояний бота в Redis |

### 3. База данных (Alembic)
При первом запуске или после удаления БД необходимо создать таблицы:
```bash
# Применить миграции до актуальной версии
python -m alembic upgrade head
```

## 🏃 Запуск

### Локально
```bash
python -m app.main
```
Mini App будет доступно по адресу `http://localhost:8000`. В Telegram Mini App используйте URL вашего сервера (локально через pyrok/ngrok или после деплоя).

### В Docker
```bash
docker build -t rent-app .
docker run --env-file .env -p 8000:8000 rent-app
```

## ☁️ Прод (Railway)
1. Проект настроен на автоматический деплой через `Dockerfile` и `railway.toml`.
2. Включен **Healthcheck** на `/health`.
3. Для **PostgreSQL**: просто добавьте сервис БД в Railway, `database.py` автоматически подхватит URL.

## 🌍 Поддерживаемые города
В системе преднастроено 29 городов в странах: 🇬🇪 Грузия, 🇹🇷 Турция, 🇷🇸 Сербия, 🇦🇲 Армения, 🇲🇪 Черногория, 🇵🇹 Португалия, 🇪🇸 Испания, 🇹🇭 Таиланд, 🇮🇩 Индонезия, 🇦🇪 ОАЭ, 🇰🇿 Казахстан, 🇺🇿 Узбекистан, 🇮🇱 Израиль и др.

---
*Rent Web V2 — эффективный агрегатор недвижимости.*
# or_rent_web
