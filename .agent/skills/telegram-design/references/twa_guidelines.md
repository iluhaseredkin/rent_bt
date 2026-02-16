# Telegram Mini Apps (TWA) Guidelines

Telegram Mini Apps — это веб-приложения, запускаемые внутри Telegram. Они позволяют создавать полноценные интерфейсы на базе веб-технологий.

## Технологический стек

-   **Frontend**: React, Vue или SolidJS.
-   **Сборка**: Vite (быстрый HMR и оптимизация).
-   **Стилизация**: Tailwind CSS (для быстрой верстки).
-   **SDK**: `@telegram-apps/sdk` или `window.Telegram.WebApp`.

## Интеграция с Telegram

### 1. Инициализация SDK

Всегда вызывайте `WebApp.ready()` при загрузке, чтобы уведомить Telegram о готовности приложения.

### 2. Темизация

Используйте CSS-переменные Telegram для обеспечения нативного вида приложения:
-   `--tg-theme-bg-color`
-   `--tg-theme-text-color`
-   `--tg-theme-button-color`
-   `--tg-theme-button-text-color`

### 3. Обработка viewport

Mini Apps имеют особенности рендеринга на мобильных устройствах. Используйте `WebApp.expand()` для расширения на весь экран и отслеживайте высоту viewport.

## Безопасность

-   **Валидация данных**: Всегда проверяйте `initData` на сервере с помощью `BOT_TOKEN`. Никогда не доверяйте данным с клиента без проверки подписи (hash).
-   **HTTPS**: Mini Apps работают только через HTTPS.

## Особенности UX

1.  **MainButton**: Используйте нативную главную кнопку Telegram (`WebApp.MainButton`) вместо кастомных кнопок внизу страницы для основных действий.
2.  **BackButton**: Управляйте нативной кнопкой "Назад" (`WebApp.BackButton`) для навигации внутри приложения.
3.  **Haptic Feedback**: Используйте тактильную отдачу (`WebApp.HapticFeedback`) для подтверждения действий пользователя.
4.  **Закрытие**: Предоставляйте пользователю возможность закрыть приложение через `WebApp.close()` после завершения целевого действия.

## Полезные ссылки

-   [Официальная документация](https://core.telegram.org/bots/webapps)
-   [Telegram Apps SDK](https://docs.telegram-apps.com/)
