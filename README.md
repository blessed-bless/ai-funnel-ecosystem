# AI Funnel Ecosystem

Воронка лидов → Telegram-бот с ИИ → mini-CRM.

Стек: Python 3.11+, FastAPI, SQLAlchemy (SQLite), aiogram 3, подключаемый AI-провайдер (`mock` или OpenAI-compatible).

## Что внутри

1. **Лендинг** (`/`) — точка входа воронки, пишет hit в CRM.
2. **Бот** — квалифицирует задачу, собирает телефон, кладёт заявку в ту же БД.
3. **CRM** (`/crm` + `/api/leads`) — список заявок и смена статуса.
4. **AI** — по умолчанию `mock` (без ключей). Для боевой модели: `AI_PROVIDER=openai_compat` + ключ.

```
landing / deep-link  →  bot + /api/chat  →  leads DB  →  /crm
```

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
mkdir data
aifunnel-api
```

Открой http://127.0.0.1:8080 и http://127.0.0.1:8080/crm.

Бот (нужен `TELEGRAM_BOT_TOKEN` в `.env`):

```bash
aifunnel-bot
```

Deep-link с лендинга: `https://t.me/<bot>?start=landing`.

Docker:

```bash
docker compose up --build api
# бот: docker compose --profile bot up --build
```

## API

| Метод | Путь | Заметка |
|---|---|---|
| GET | `/health` | живость |
| POST | `/api/funnel/hit` | источник + utm → новый лид |
| POST | `/api/chat` | диалог с ИИ, создание/обновление лида |
| GET/POST/PATCH | `/api/leads` | CRM, заголовок `X-CRM-Token` |

## Тесты

```bash
pytest -q
```

## Автор

Богдан Щербинин ([blessed-bless](https://github.com/blessed-bless))

MIT.
