# Arizona Market Monitor Storage

Flask-сервер для Arizona Market Monitor:

- хранит JSON-документы бота: `users`, `keys`, `bans`, `items`, `market_cache`, `market_actual`;
- отдает Lua-скрипту проверку `script_key` и импорт настроек по `config_key`;
- может проксировать `api.arz.market`, не раскрывая настоящий `MARKET_AUTH_KEY` клиентам.

## Переменные окружения

Обязательные для записи JSON:

```env
AMM_STORAGE_KEY=long-random-secret
```

Опциональные:

```env
AMM_DATA_DIR=data
MARKET_AUTH_KEY=your-live-arz-market-token
AMM_CLIENT_KEYS=ADMIN_KEY,ANOTHER_STATIC_KEY
MARKET_API_BASE=https://api.arz.market/api
REQUEST_TIMEOUT=12
PORT=5000
```

Не коммить реальные токены в репозиторий. `config.json` бота должен хранить только URL сайта и имя env-переменной с ключом.

## API

`GET /health` - проверка сервера.

`GET /api/storage` - список документов, нужен `X-Storage-Key`.

`GET /api/storage/users` - получить JSON.

`PUT /api/storage/users` - заменить JSON.

`PATCH /api/storage/users` - слить поля JSON-объекта.

Доступные документы: `users`, `keys`, `bans`, `items`, `market_cache`, `market_actual`.

`GET /api/lua/access/<script_key>` - проверка Lua-ключа.

`GET /api/lua/config/<config_key>` - импорт настроек пользователя по ключу конфига.

`GET /api/public/items` - публичный список предметов.

`/api/selectMarketplace/...` и `/api/getSelectedMarketplace/...` - прокси рынка. Клиентский ключ можно передать через `authKey`, `X-Client-Key`, `X-Storage-Key`, `Authorization: Bearer ...`, `?key=...`.
