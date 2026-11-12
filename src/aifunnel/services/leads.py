import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.ai.base import AIProvider, ChatTurn
from aifunnel.models import ConversationMessage, Lead, LeadStatus
from aifunnel.schemas import LeadCreate, LeadUpdate


PHONE_RE = re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")


async def create_lead(session: AsyncSession, payload: LeadCreate) -> Lead:
    lead = Lead(**payload.model_dump())
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    return lead


async def get_lead(session: AsyncSession, lead_id: int) -> Lead | None:
    return await session.get(Lead, lead_id)


async def list_leads(session: AsyncSession, limit: int = 100) -> list[Lead]:
    result = await session.execute(select(Lead).order_by(Lead.id.desc()).limit(limit))
    return list(result.scalars().all())


async def update_lead(session: AsyncSession, lead: Lead, payload: LeadUpdate) -> Lead:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, key, value)
    await session.commit()
    await session.refresh(lead)
    return lead


async def get_or_create_by_telegram(
    session: AsyncSession,
    *,
    telegram_id: str,
    source: str,
    username: str | None = None,
) -> Lead:
    result = await session.execute(select(Lead).where(Lead.telegram_id == telegram_id))
    lead = result.scalar_one_or_none()
    if lead:
        if username and lead.telegram_username != username:
            lead.telegram_username = username
            await session.commit()
            await session.refresh(lead)
        return lead
    return await create_lead(
        session,
        LeadCreate(
            source=source,
            telegram_id=telegram_id,
            telegram_username=username,
            status=LeadStatus.QUALIFYING.value,
        ),
    )


async def append_message(session: AsyncSession, lead_id: int, role: str, content: str) -> None:
    session.add(ConversationMessage(lead_id=lead_id, role=role, content=content))
    await session.commit()


async def load_history(session: AsyncSession, lead_id: int, limit: int = 20) -> list[ChatTurn]:
    result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.lead_id == lead_id)
        .order_by(ConversationMessage.id.desc())
        .limit(limit)
    )
    rows = list(reversed(result.scalars().all()))
    return [ChatTurn(role=row.role, content=row.content) for row in rows]


def extract_phone(text: str) -> str | None:
    match = PHONE_RE.search(text)
    return match.group(0) if match else None


async def chat_with_lead(
    session: AsyncSession,
    ai: AIProvider,
    *,
    lead: Lead,
    message: str,
) -> tuple[Lead, str, bool]:
    history = await load_history(session, lead.id)
    await append_message(session, lead.id, "user", message)

    phone = extract_phone(message)
    if phone and not lead.phone:
        lead.phone = phone
    if not lead.need and len(message) > 20 and not phone:
        lead.need = message[:500]
    if lead.status == LeadStatus.NEW.value:
        lead.status = LeadStatus.QUALIFYING.value

    reply = await ai.reply(history, message)
    await append_message(session, lead.id, "assistant", reply)

    ready = bool(lead.phone and (lead.need or lead.summary))
    if ready and lead.status not in {LeadStatus.HANDED.value, LeadStatus.CLOSED.value}:
        lead.status = LeadStatus.READY.value
        if not lead.summary:
            lead.summary = f"Источник: {lead.source}. Нужда: {lead.need or '—'}. Телефон: {lead.phone}."

    await session.commit()
    await session.refresh(lead)
    return lead, reply, ready
