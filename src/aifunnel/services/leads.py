import csv
import io
import re

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.ai.base import AIProvider, ChatTurn
from aifunnel.cache import stats_cache
from aifunnel.models import ConversationMessage, Lead, LeadNote, LeadStatus, OutboxJob
from aifunnel.schemas import LeadCreate, LeadUpdate
from aifunnel.services import audit, outbox

PHONE_RE = re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


async def create_lead(session: AsyncSession, payload: LeadCreate) -> Lead:
    data = payload.model_dump()
    lead = Lead(**data)
    session.add(lead)
    await session.flush()
    await audit.record(
        session,
        action="lead.created",
        entity_id=lead.id,
        payload={"source": lead.source, "status": lead.status},
        commit=False,
    )
    await session.commit()
    await session.refresh(lead)
    stats_cache.invalidate()
    return lead


async def get_lead(session: AsyncSession, lead_id: int) -> Lead | None:
    return await session.get(Lead, lead_id)


async def list_leads(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    source: str | None = None,
    q: str | None = None,
    tag: str | None = None,
) -> list[Lead]:
    query = select(Lead).order_by(Lead.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 500))
    if status:
        query = query.where(Lead.status == status)
    if source:
        query = query.where(Lead.source == source)
    if tag:
        query = query.where(Lead.tags.contains(tag))
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                Lead.phone.ilike(like),
                Lead.name.ilike(like),
                Lead.email.ilike(like),
                Lead.need.ilike(like),
                Lead.summary.ilike(like),
                Lead.telegram_username.ilike(like),
                Lead.telegram_id.ilike(like),
            )
        )
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_lead(session: AsyncSession, lead: Lead, payload: LeadUpdate) -> Lead:
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(lead, key, value)
    await audit.record(
        session,
        action="lead.updated",
        entity_id=lead.id,
        payload=changes,
        commit=False,
    )
    await session.commit()
    await session.refresh(lead)
    stats_cache.invalidate()
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


async def append_messages(
    session: AsyncSession,
    lead_id: int,
    items: list[tuple[str, str]],
    *,
    commit: bool = False,
) -> None:
    for role, content in items:
        session.add(ConversationMessage(lead_id=lead_id, role=role, content=content))
    if commit:
        await session.commit()


async def load_history(session: AsyncSession, lead_id: int, limit: int = 20) -> list[ChatTurn]:
    rows = await list_messages(session, lead_id, limit=limit)
    return [ChatTurn(role=row.role, content=row.content) for row in rows]


async def list_messages(
    session: AsyncSession,
    lead_id: int,
    *,
    limit: int = 100,
) -> list[ConversationMessage]:
    result = await session.execute(
        select(ConversationMessage)
        .where(ConversationMessage.lead_id == lead_id)
        .order_by(ConversationMessage.id.desc())
        .limit(min(max(limit, 1), 500))
    )
    return list(reversed(result.scalars().all()))


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
    if lead.tags:
        score += 5
    return min(score, 100)


async def chat_with_lead(
    session: AsyncSession,
    ai: AIProvider,
    *,
    lead: Lead,
    message: str,
) -> tuple[Lead, str, bool]:
    history = await load_history(session, lead.id)

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
    await append_messages(
        session,
        lead.id,
        [("user", message), ("assistant", reply)],
        commit=False,
    )

    lead.score = score_lead(lead)
    ready = bool(lead.phone and (lead.need or lead.summary))
    enqueue_ready = False
    if ready and lead.status not in {LeadStatus.HANDED.value, LeadStatus.CLOSED.value, LeadStatus.SPAM.value}:
        if lead.status != LeadStatus.READY.value:
            enqueue_ready = True
        lead.status = LeadStatus.READY.value
        lead.stage_slug = "ready"
        if not lead.summary:
            lead.summary = (
                f"Источник: {lead.source}. Нужда: {lead.need or '—'}. Телефон: {lead.phone}."
            )

    await session.commit()
    if enqueue_ready:
        await outbox.enqueue(
            session,
            kind="notify_ready_lead",
            payload={
                "lead_id": lead.id,
                "phone": lead.phone,
                "source": lead.source,
                "score": lead.score,
                "need": lead.need,
            },
        )
    await session.refresh(lead)
    stats_cache.invalidate()
    return lead, reply, ready


async def stats(session: AsyncSession) -> dict[str, int]:
    cached = stats_cache.get("main")
    if cached is not None:
        return cached

    lead_row = await session.execute(
        select(
            func.count().label("total"),
            func.sum(case((Lead.status == LeadStatus.READY.value, 1), else_=0)).label("ready"),
            func.sum(case((Lead.status == LeadStatus.QUALIFYING.value, 1), else_=0)).label("qualifying"),
        ).select_from(Lead)
    )
    total, ready, qualifying = lead_row.one()
    pending = await session.scalar(
        select(func.count()).select_from(OutboxJob).where(OutboxJob.status == "pending")
    ) or 0
    result = {
        "leads_total": int(total or 0),
        "leads_ready": int(ready or 0),
        "leads_qualifying": int(qualifying or 0),
        "outbox_pending": int(pending),
    }
    stats_cache.set("main", result)
    return result


async def add_note(
    session: AsyncSession,
    *,
    lead_id: int,
    body: str,
    author: str = "admin",
) -> LeadNote:
    note = LeadNote(lead_id=lead_id, body=body.strip(), author=author)
    session.add(note)
    await audit.record(
        session,
        action="lead.note_added",
        actor=author,
        entity_id=lead_id,
        payload={"body": body[:200]},
        commit=False,
    )
    await session.commit()
    await session.refresh(note)
    return note


async def list_notes(session: AsyncSession, lead_id: int, *, limit: int = 50) -> list[LeadNote]:
    result = await session.execute(
        select(LeadNote)
        .where(LeadNote.lead_id == lead_id)
        .order_by(LeadNote.id.desc())
        .limit(min(max(limit, 1), 200))
    )
    return list(result.scalars().all())


def export_leads_csv(leads: list[Lead]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=[
            "id",
            "source",
            "status",
            "stage_slug",
            "name",
            "phone",
            "email",
            "telegram_id",
            "telegram_username",
            "need",
            "budget_note",
            "tags",
            "score",
            "summary",
        ],
    )
    writer.writeheader()
    for lead in leads:
        writer.writerow(
            {
                "id": lead.id,
                "source": lead.source,
                "status": lead.status,
                "stage_slug": lead.stage_slug or "",
                "name": lead.name or "",
                "phone": lead.phone or "",
                "email": lead.email or "",
                "telegram_id": lead.telegram_id or "",
                "telegram_username": lead.telegram_username or "",
                "need": lead.need or "",
                "budget_note": lead.budget_note or "",
                "tags": lead.tags or "",
                "score": lead.score,
                "summary": lead.summary or "",
            }
        )
    return buf.getvalue()
