# Запуск на новом Telegram-аккаунте

1. Создай Telegram API ID/API HASH на своём аккаунте разработчика Telegram.
2. Локально запусти `python generate_session.py` и авторизуй именно новый аккаунт.
3. Сохрани полученный `StringSession` в Railway Variable `TELEGRAM_SESSION`.
4. Не добавляй StringSession, API hash или bot token в GitHub.
5. Для первого запуска оставь консервативные настройки из `.env.example`:
   - `CONCURRENCY=1`
   - `MIN_API_REQUEST_INTERVAL=2.5`
   - `REQUEST_DELAY=2.5`
   - `SCAN_INTERVAL=180`
   - `PAGE_LIMIT=25`
   - `MAX_PAGES_PER_GIFT=1`
6. Фильтры продавцов включены:
   - `FILTER_ARABIC_TEXT=true`
   - `MAX_SELLER_LEVEL=2`
   - `SKIP_UNKNOWN_SELLER_LEVEL=true`

Этот проект не содержит готовой Telegram-сессии. Перед деплоем нужно указать свою новую `TELEGRAM_SESSION` в Railway.


### Stability setting
`API_REQUEST_TIMEOUT=45` prevents a stalled Telegram request from freezing a scan indefinitely. Railway logs now also show scan progress every 10 gift types.
