import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.ai.base import AIProvider, ChatTurn
from aifunnel.models import ConversationMessage, Lead, LeadStatus, OutboxJob
from aifunnel.schemas import LeadCreate, LeadUpdate
from aifunnel.services import audit, outbox

PHONE_RE = re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


async def create_lead(session: AsyncSession, payload: LeadCreate) -> Lead:
    lead = Lead(**payload.model_dump())
    session.add(lead)
    await session.commit()
    await session.refresh(lead)
    await audit.record(
        session,
        action="lead.created",
        entity_id=lead.id,
        payload={"source": lead.source, "status": lead.status},
    )
    return lead


async def get_lead(session: AsyncSession, lead_id: int) -> Lead | None:
    return await session.get(Lead, lead_id)


async def list_leads(
    session: AsyncSession,
    *,
    limit: int = 100,
    status: str | None = None,
    source: str | None = None,
) -> list[Lead]:
    query = select(Lead).order_by(Lead.id.desc()).limit(min(max(limit, 1), 500))
    if status:
        query = query.where(Lead.status == status)
    if source:
        query = query.where(Lead.source == source)
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_lead(session: AsyncSession, lead: Lead, payload: LeadUpdate) -> Lead:
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(lead, key, value)
    await session.commit()
    await session.refresh(lead)
    await audit.record(
        session,
        action="lead.updated",
        entity_id=lead.id,
        payload=changes,
    )
    return lead


async def get_or_create_by_telegram(
    session: AsyncSession,
    *,
    telegram_id: str,
    source: str,
    username: str | None = None,
    funnel_id: int | None = None,
) -> Lead:
    result = await session.execute(select(Lead).where(Lead.telegram_id == telegram_id))
    lead = result.scalar_one_or_none()
    if lead:
        dirty = False
        if username and lead.telegram_username != username:
            lead.telegram_username = username
            dirty = True
        if funnel_id and lead.funnel_id is None:
            lead.funnel_id = funnel_id
            dirty = True
        if dirty:
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
            funnel_id=funnel_id,
            stage_slug="qualify",
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


def extract_email(text: str) -> str | None:
    match = EMAIL_RE.search(text)
    return match.group(0) if match else None


def score_lead(lead: Lead) -> int:
    score = 0
    if lead.need:
        score += 30
    if lead.phone:
        score += 40
    if lead.email:
        score += 10
    if lead.telegram_id:
        score += 10
    if lead.budget_note:
        score += 10
    return min(score, 100)


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
    email = extract_email(message)
    if phone and not lead.phone:
        lead.phone = phone
    if email and not lead.email:
        lead.email = email
    if not lead.need and len(message) > 20 and not phone:
        lead.need = message[:500]
    if lead.status == LeadStatus.NEW.value:
        lead.status = LeadStatus.QUALIFYING.value
        lead.stage_slug = lead.stage_slug or "qualify"

    reply = await ai.reply(history, message)
    await append_message(session, lead.id, "assistant", reply)

    lead.score = score_lead(lead)
    ready = bool(lead.phone and (lead.need or lead.summary))
    if ready and lead.status not in {LeadStatus.HANDED.value, LeadStatus.CLOSED.value, LeadStatus.SPAM.value}:
        lead.status = LeadStatus.READY.value
        lead.stage_slug = "ready"
        if not lead.summary:
            lead.summary = (
                f"Источник: {lead.source}. Нужда: {lead.need or '—'}. Телефон: {lead.phone}."
            )
        await session.commit()
        await outbox.enqueue(
            session,
            kind="notify_ready_lead",
            payload={"lead_id": lead.id, "phone": lead.phone, "source": lead.source},
        )
    else:
        await session.commit()

    await session.refresh(lead)
    return lead, reply, ready


async def stats(session: AsyncSession) -> dict[str, int]:
    total = await session.scalar(select(func.count()).select_from(Lead)) or 0
    ready = await session.scalar(
        select(func.count()).select_from(Lead).where(Lead.status == LeadStatus.READY.value)
    ) or 0
    qualifying = await session.scalar(
        select(func.count()).select_from(Lead).where(Lead.status == LeadStatus.QUALIFYING.value)
    ) or 0
    pending = await session.scalar(
        select(func.count()).select_from(OutboxJob).where(OutboxJob.status == "pending")
    ) or 0
    return {
        "leads_total": int(total),
        "leads_ready": int(ready),
        "leads_qualifying": int(qualifying),
        "outbox_pending": int(pending),
    }
