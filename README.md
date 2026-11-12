# AI Funnel Ecosystem

Воронка лидов → Telegram AI-бот → mini-CRM → outbox-воркер.

Стек: Python 3.11+, FastAPI, SQLAlchemy async (SQLite), aiogram 3, mock/OpenAI-compatible AI с retry и circuit breaker.

## Возможности

- Лендинг с hit в воронку (`/api/funnel/hit`)
- Диалог `/api/chat` и Telegram-бот с квалификацией лида
- CRM UI `/crm` + REST `/api/leads`, `/api/stats`, `/api/funnels`
- Security: CRM-токен, rate-limit, security headers, request-id, CORS
- Reliability: `/health` + `/ready`, AI retries/fallback, outbox jobs, graceful worker stop
- Лёгкие SQLite-миграции колонок на старте

```
landing → bot/chat → leads + audit → outbox worker → CRM
```

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
mkdir data
aifunnel-api
```

Отдельно:

```bash
aifunnel-worker
aifunnel-bot
```

Docker:

```bash
docker compose up --build api worker
```

## Тесты

```bash
pytest -q
```

## Автор

Богдан Щербинин ([blessed-bless](https://github.com/blessed-bless))

MIT.
