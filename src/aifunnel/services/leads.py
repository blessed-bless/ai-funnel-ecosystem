import csv
import io
import re
from datetime import datetime, timezone

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.ai.base import AIProvider, ChatTurn
from aifunnel.cache import stats_cache
from aifunnel.domain.phones import normalize_phone
from aifunnel.models import (
    ALLOWED_STAGE_TRANSITIONS,
    ConversationMessage,
    Lead,
    LeadNote,
    LeadStatus,
    OutboxJob,
)
from aifunnel.schemas import LeadCreate, LeadUpdate
from aifunnel.services import activities, audit, outbox

PHONE_RE = re.compile(r"(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _active_leads():
    return Lead.deleted_at.is_(None)


async def create_lead(session: AsyncSession, payload: LeadCreate) -> Lead:
    data = payload.model_dump()
    phone = data.get("phone")
    data["phone_normalized"] = normalize_phone(phone)

    if data["phone_normalized"]:
        existing = await find_by_phone(session, data["phone_normalized"], include_deleted=False)
        if existing:
            # dedupe: обогащаем существующий лид вместо дубля
            merged = False
            for key in ("name", "email", "need", "budget_note", "telegram_id", "telegram_username", "tags"):
                val = data.get(key)
                if val and not getattr(existing, key):
                    setattr(existing, key, val)
                    merged = True
            if data.get("source") and existing.source == "direct":
                existing.source = data["source"]
                merged = True
            if merged:
                await activities.add_activity(
                    session,
                    lead_id=existing.id,
                    kind="dedupe_merge",
                    message="Объединили повторное обращение по телефону",
                    meta={"incoming_source": data.get("source")},
                    commit=False,
                )
                await session.commit()
                await session.refresh(existing)
                stats_cache.invalidate()
            return existing

    lead = Lead(**{k: v for k, v in data.items() if k in Lead.__table__.columns.keys()})
    session.add(lead)
    await session.flush()
    await audit.record(
        session,
        action="lead.created",
        entity_id=lead.id,
        payload={"source": lead.source, "status": lead.status},
        commit=False,
    )
    await activities.add_activity(
        session,
        lead_id=lead.id,
        kind="created",
        message=f"Лид создан из источника {lead.source}",
        commit=False,
    )
    await session.commit()
    await session.refresh(lead)
    stats_cache.invalidate()
    return lead


async def find_by_phone(
    session: AsyncSession,
    phone_normalized: str,
    *,
    include_deleted: bool = False,
) -> Lead | None:
    query = select(Lead).where(Lead.phone_normalized == phone_normalized).order_by(Lead.id.desc())
    if not include_deleted:
        query = query.where(_active_leads())
    result = await session.execute(query.limit(1))
    return result.scalar_one_or_none()


async def get_lead(session: AsyncSession, lead_id: int, *, include_deleted: bool = False) -> Lead | None:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        return None
    if lead.deleted_at is not None and not include_deleted:
        return None
    return lead


async def list_leads(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
    status: str | None = None,
    source: str | None = None,
    q: str | None = None,
    tag: str | None = None,
    manager_id: int | None = None,
    include_deleted: bool = False,
) -> list[Lead]:
    query = select(Lead).order_by(Lead.id.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 500))
    if not include_deleted:
        query = query.where(_active_leads())
    if status:
        query = query.where(Lead.status == status)
    if source:
        query = query.where(Lead.source == source)
    if manager_id is not None:
        query = query.where(Lead.assigned_manager_id == manager_id)
    if tag:
        query = query.where(Lead.tags.contains(tag))
    if q:
        like = f"%{q.strip()}%"
        query = query.where(
            or_(
                Lead.phone.ilike(like),
                Lead.phone_normalized.ilike(like),
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


def assert_status_transition(old: str, new: str) -> None:
    if old == new:
        return
    allowed = ALLOWED_STAGE_TRANSITIONS.get(old, set())
    if new not in allowed:
        raise ValueError(f"Переход статуса {old} → {new} запрещён. Можно: {sorted(allowed)}")


async def update_lead(
    session: AsyncSession,
    lead: Lead,
    payload: LeadUpdate,
    *,
    actor: str = "system",
) -> Lead:
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"]:
        assert_status_transition(lead.status, changes["status"])
    if "phone" in changes:
        changes["phone_normalized"] = normalize_phone(changes.get("phone"))

    old_status = lead.status
    for key, value in changes.items():
        if key in Lead.__table__.columns.keys():
            setattr(lead, key, value)

    await audit.record(
        session,
        action="lead.updated",
        actor=actor,
        entity_id=lead.id,
        payload=changes,
        commit=False,
    )
    if "status" in changes and changes["status"] != old_status:
        await activities.add_activity(
            session,
            lead_id=lead.id,
            kind="status_change",
            actor=actor,
            message=f"Статус: {old_status} → {changes['status']}",
            meta={"from": old_status, "to": changes["status"]},
            commit=False,
        )
        if changes["status"] == LeadStatus.READY.value:
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
                commit=False,
            )
            await outbox.enqueue(
                session,
                kind="notify_telegram_manager",
                payload={"lead_id": lead.id},
                commit=False,
            )
    await session.commit()
    await session.refresh(lead)
    stats_cache.invalidate()
    return lead


async def soft_delete(session: AsyncSession, lead: Lead, *, actor: str = "system") -> Lead:
    lead.deleted_at = datetime.now(timezone.utc)
    await activities.add_activity(
        session,
        lead_id=lead.id,
        kind="soft_delete",
        actor=actor,
        message="Лид помечен удалённым",
        commit=False,
    )
    await session.commit()
    await session.refresh(lead)
    stats_cache.invalidate()
    return lead


async def restore(session: AsyncSession, lead: Lead, *, actor: str = "system") -> Lead:
    lead.deleted_at = None
    await activities.add_activity(
        session,
        lead_id=lead.id,
        kind="restore",
        actor=actor,
        message="Лид восстановлен",
        commit=False,
    )
    await session.commit()
    await session.refresh(lead)
    stats_cache.invalidate()
    return lead


async def bulk_update_status(
    session: AsyncSession,
    lead_ids: list[int],
    status: str,
    *,
    actor: str = "system",
) -> tuple[int, list[str]]:
    updated = 0
    failed: list[str] = []
    for lead_id in lead_ids:
        lead = await get_lead(session, lead_id)
        if not lead:
            failed.append(f"{lead_id}: не найден")
            continue
        try:
            await update_lead(session, lead, LeadUpdate(status=status, stage_slug=status), actor=actor)
            updated += 1
        except ValueError as exc:
            failed.append(f"{lead_id}: {exc}")
    return updated, failed


async def get_or_create_by_telegram(
    session: AsyncSession,
    *,
    telegram_id: str,
    source: str,
    username: str | None = None,
    funnel_id: int | None = None,
    workspace_id: int | None = None,
) -> Lead:
    result = await session.execute(
        select(Lead).where(Lead.telegram_id == telegram_id, _active_leads())
    )
    lead = result.scalar_one_or_none()
    if lead:
        dirty = False
        if username and lead.telegram_username != username:
            lead.telegram_username = username
            dirty = True
        if funnel_id and lead.funnel_id is None:
            lead.funnel_id = funnel_id
            dirty = True
        if workspace_id and lead.workspace_id is None:
            lead.workspace_id = workspace_id
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
            workspace_id=workspace_id,
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
    if lead.assigned_manager_id:
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
        lead.phone_normalized = normalize_phone(phone)
    if email and not lead.email:
        lead.email = email
    if not lead.need and len(message) > 20:
        cleaned_need = PHONE_RE.sub("", message)
        cleaned_need = EMAIL_RE.sub("", cleaned_need).strip(" ,.;\n\t")
        if len(cleaned_need) > 12:
            lead.need = cleaned_need[:500]
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
    await activities.add_activity(
        session,
        lead_id=lead.id,
        kind="chat",
        message="Сообщение в диалоге",
        meta={"chars": len(message)},
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
        await outbox.enqueue(session, kind="notify_telegram_manager", payload={"lead_id": lead.id})
        await activities.add_activity(
            session,
            lead_id=lead.id,
            kind="ready",
            message="Лид готов к менеджеру",
            commit=True,
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
            func.sum(case((Lead.status == LeadStatus.QUALIFYING.value, 1), else_=0)).label(
                "qualifying"
            ),
        )
        .select_from(Lead)
        .where(_active_leads())
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
    await activities.add_activity(
        session,
        lead_id=lead_id,
        kind="note",
        actor=author,
        message=body[:240],
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
            "phone_normalized",
            "email",
            "telegram_id",
            "telegram_username",
            "need",
            "budget_note",
            "tags",
            "score",
            "assigned_manager_id",
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
                "phone_normalized": lead.phone_normalized or "",
                "email": lead.email or "",
                "telegram_id": lead.telegram_id or "",
                "telegram_username": lead.telegram_username or "",
                "need": lead.need or "",
                "budget_note": lead.budget_note or "",
                "tags": lead.tags or "",
                "score": lead.score,
                "assigned_manager_id": lead.assigned_manager_id or "",
                "summary": lead.summary or "",
            }
        )
    return buf.getvalue()


async def import_leads_csv(session: AsyncSession, content: str, *, source: str = "csv_import") -> dict:
    reader = csv.DictReader(io.StringIO(content))
    created = 0
    merged = 0
    errors: list[str] = []
    for idx, row in enumerate(reader, start=2):
        try:
            phone = (row.get("phone") or "").strip() or None
            norm = normalize_phone(phone) if phone else None
            before = await find_by_phone(session, norm, include_deleted=False) if norm else None
            lead = await create_lead(
                session,
                LeadCreate(
                    source=(row.get("source") or source).strip() or source,
                    name=(row.get("name") or None) or None,
                    phone=phone,
                    email=(row.get("email") or None) or None,
                    need=(row.get("need") or None) or None,
                    tags=(row.get("tags") or None) or None,
                    budget_note=(row.get("budget_note") or None) or None,
                    status=(row.get("status") or "new").strip() or "new",
                ),
            )
            if before and before.id == lead.id:
                merged += 1
            else:
                created += 1
        except Exception as exc:
            errors.append(f"row {idx}: {exc}")
    return {"created": created, "merged": merged, "errors": errors[:50]}
