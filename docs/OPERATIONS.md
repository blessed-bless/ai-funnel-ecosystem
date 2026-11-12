# Эксплуатация AI Funnel Ecosystem

## Процессы

| Команда | Роль |
|---|---|
| `aifunnel-api` | лендинг, CRM UI, REST, метрики |
| `aifunnel-worker` | outbox → webhook |
| `aifunnel-bot` | Telegram polling |

Общая SQLite/БД через `DATABASE_URL`. Для нескольких реплик API включи `REDIS_URL`.

## Health

- `GET /health` — процесс жив
- `GET /ready` — БД + AI circuit + Redis
- `GET /metrics` — Prometheus text

Docker Compose: `api` с `healthcheck` на `/health`.

## Секреты

В `APP_ENV=production` старт падает, если оставлены дефолтные:

- `CRM_API_TOKEN`
- `JWT_SECRET`
- `ADMIN_PASSWORD`

## Webhook

При статусе лида `ready` воркер шлёт `lead.ready` на `WEBHOOK_URL`.
Подпись: заголовок `X-Aifunnel-Signature` = HMAC-SHA256(`WEBHOOK_SECRET`, body).

## Миграции

```bash
alembic upgrade head
```

На старте API дополнительно делает `create_all` и лёгкий ALTER для старых SQLite.
