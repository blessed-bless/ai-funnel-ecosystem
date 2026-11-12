# AI Funnel Ecosystem

Воронка лидов → Telegram AI-бот → mini-CRM → outbox-воркер.

Стек: Python 3.11+, FastAPI, SQLAlchemy async (SQLite), aiogram 3, mock/OpenAI-compatible AI с retry и circuit breaker.

## Возможности

- Лендинг с hit в воронку (`/api/funnel/hit`)
- Диалог `/api/chat` и Telegram-бот с квалификацией лида
- Workspace + managers (`/api/managers`), назначение менеджера на лид
- Soft-delete / restore, dedupe по нормализованному телефону
- Правила переходов статуса, timeline (`/api/leads/{id}/activities`)
- CRM UI: фильтры, заметки, timeline на карточке
- REST: search/tag/manager, notes, CSV import/export, bulk status, messages, stats, funnels
- Outbox: webhook + notify менеджеру в Telegram
- Performance: SQLite WAL, TTL-кэш stats/funnel, batch messages
- Auth: `X-CRM-Token` или JWT; HTML CRM за cookie-логином
- Security: rate-limit (memory/Redis), headers, request-id, CORS, pbkdf2
- Reliability: `/health` + `/ready`, AI retries/fallback, Alembic
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
