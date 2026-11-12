# Changelog

## 0.6.0

- Workspace и managers (`/api/managers`), привязка воронки и лида к workspace
- Soft-delete / restore лидов, фильтр `include_deleted`
- Dedupe по `phone_normalized` при create/import
- Правила переходов статуса (`ALLOWED_STAGE_TRANSITIONS`)
- Timeline: `lead_activities` + `/api/leads/{id}/activities`
- CSV import + bulk status (с `failed[]`)
- Outbox kind `notify_telegram_manager` + `TELEGRAM_MANAGER_CHAT_ID`
- CRM UI: фильтры, заметки, timeline на карточке
- Alembic `20261112_0003`

## 0.5.0

- Notes, tags, search, CSV export, webhook deliveries, CRM cookie auth hardening
