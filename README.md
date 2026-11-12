# AI Funnel Ecosystem

Воронка лидов → Telegram AI-бот → mini-CRM → outbox-воркер.

Стек: Python 3.11+, FastAPI, SQLAlchemy async (SQLite), aiogram 3, mock/OpenAI-compatible AI с retry и circuit breaker.

## Возможности

- Лендинг с hit в воронку (`/api/funnel/hit`)
- Диалог `/api/chat` и Telegram-бот с квалификацией лида
- CRM UI `/crm` + карточка лида с диалогом `/crm/leads/{id}`
- REST: `/api/leads`, `/api/leads/{id}/messages`, `/api/stats`, `/api/funnels`
- Auth: `X-CRM-Token` или JWT (`/api/auth/login`, `/me`); HTML CRM за cookie-логином
- Security: rate-limit (memory/Redis), headers, request-id, CORS, pbkdf2
- Reliability: `/health` + `/ready`, AI retries/fallback, outbox → webhook, Alembic
- Metrics: `/metrics` (Prometheus text)

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

## Миграции

```bash
alembic upgrade head
```

На старте API также делает `create_all` + лёгкий ALTER для старых SQLite.

## Тесты

```bash
pytest -q
```

## Автор

Богдан Щербинин ([blessed-bless](https://github.com/blessed-bless))

MIT.
