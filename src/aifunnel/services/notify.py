import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.config import Settings
from aifunnel.models import Lead, Manager

logger = logging.getLogger("aifunnel.notify")


async def telegram_manager_about_lead(
    session: AsyncSession,
    settings: Settings,
    *,
    lead_id: int,
) -> None:
    lead = await session.get(Lead, lead_id)
    if not lead:
        logger.warning("notify skip: lead %s missing", lead_id)
        return

    chat_id = None
    if lead.assigned_manager_id:
        manager = await session.get(Manager, lead.assigned_manager_id)
        chat_id = manager.telegram_chat_id if manager else None
    if not chat_id:
        # fallback: первый активный менеджер с chat_id в workspace
        result = await session.execute(
            select(Manager)
            .where(Manager.is_active == 1, Manager.telegram_chat_id.is_not(None))
            .order_by(Manager.id.asc())
            .limit(1)
        )
        manager = result.scalar_one_or_none()
        chat_id = manager.telegram_chat_id if manager else None

    if not chat_id and settings.telegram_manager_chat_id:
        chat_id = settings.telegram_manager_chat_id
    if not chat_id:
        logger.info("telegram notify skipped: no manager chat_id for lead=%s", lead_id)
        return
    if not settings.telegram_bot_token:
        logger.info("telegram notify skipped: empty TELEGRAM_BOT_TOKEN")
        return

    text = (
        f"Новая готовая заявка #{lead.id}\n"
        f"Источник: {lead.source}\n"
        f"Телефон: {lead.phone or '—'}\n"
        f"Score: {lead.score}\n"
        f"Нужда: {(lead.need or '—')[:300]}\n"
        f"CRM: {settings.api_public_url.rstrip('/')}/crm/leads/{lead.id}"
    )
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=12.0) as client:
        response = await client.post(url, json={"chat_id": chat_id, "text": text})
        if response.status_code >= 400:
            raise RuntimeError(f"telegram notify HTTP {response.status_code}: {response.text[:300]}")
    logger.info("telegram notify ok lead_id=%s chat_id=%s", lead_id, chat_id)
