from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.ai import build_ai
from aifunnel.api.auth import AuthContext, require_crm_token
from aifunnel.api.deps import enforce_api_limit, enforce_chat_limit
from aifunnel.db import get_session
from aifunnel.observability import metrics
from aifunnel.schemas import (
    ChatIn,
    ChatOut,
    FunnelHitIn,
    LeadCreate,
    LeadOut,
    LeadUpdate,
    MessageOut,
    NoteCreate,
    NoteOut,
    StatsOut,
)
from aifunnel.services import funnels as funnel_service
from aifunnel.services import leads as lead_service

router = APIRouter(prefix="/api", tags=["leads"])


@router.post("/funnel/hit", response_model=LeadOut, dependencies=[Depends(enforce_api_limit)])
async def funnel_hit(
    payload: FunnelHitIn,
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    source = payload.source
    if payload.utm_campaign:
        source = f"{source}:{payload.utm_campaign}"
    funnel = None
    if payload.funnel_slug:
        funnel = await funnel_service.get_by_slug(session, payload.funnel_slug)
        if funnel is None:
            funnel = await funnel_service.ensure_default_funnel(session)
    lead = await lead_service.create_lead(
        session,
        LeadCreate(
            source=source,
            status="new",
            funnel_id=funnel.id if funnel else None,
            stage_slug="awareness",
        ),
    )
    metrics.inc("aifunnel_funnel_hits_total", labels={"source": payload.source})
    return LeadOut.model_validate(lead)


@router.get("/leads", response_model=list[LeadOut], dependencies=[Depends(require_crm_token)])
async def api_list_leads(
    status: str | None = Query(default=None),
    source: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=120),
    tag: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[LeadOut]:
    items = await lead_service.list_leads(
        session,
        limit=limit,
        offset=offset,
        status=status,
        source=source,
        q=q,
        tag=tag,
    )
    return [LeadOut.model_validate(item) for item in items]


@router.get("/leads/export.csv", dependencies=[Depends(require_crm_token)])
async def api_export_leads_csv(
    status: str | None = Query(default=None),
    q: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> Response:
    items = await lead_service.list_leads(session, limit=500, status=status, q=q)
    csv_text = lead_service.export_leads_csv(items)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.post("/leads", response_model=LeadOut, dependencies=[Depends(require_crm_token)])
async def api_create_lead(
    payload: LeadCreate,
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    lead = await lead_service.create_lead(session, payload)
    return LeadOut.model_validate(lead)


@router.get("/leads/{lead_id}", response_model=LeadOut, dependencies=[Depends(require_crm_token)])
async def api_get_lead(lead_id: int, session: AsyncSession = Depends(get_session)) -> LeadOut:
    lead = await lead_service.get_lead(session, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Лид не найден")
    return LeadOut.model_validate(lead)


@router.patch("/leads/{lead_id}", response_model=LeadOut, dependencies=[Depends(require_crm_token)])
async def api_patch_lead(
    lead_id: int,
    payload: LeadUpdate,
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    lead = await lead_service.get_lead(session, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Лид не найден")
    lead = await lead_service.update_lead(session, lead, payload)
    return LeadOut.model_validate(lead)


@router.get("/stats", response_model=StatsOut, dependencies=[Depends(require_crm_token)])
async def api_stats(session: AsyncSession = Depends(get_session)) -> StatsOut:
    return StatsOut(**await lead_service.stats(session))


@router.get(
    "/leads/{lead_id}/messages",
    response_model=list[MessageOut],
    dependencies=[Depends(require_crm_token)],
)
async def api_lead_messages(
    lead_id: int,
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[MessageOut]:
    lead = await lead_service.get_lead(session, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Лид не найден")
    rows = await lead_service.list_messages(session, lead_id, limit=limit)
    return [MessageOut.model_validate(row) for row in rows]


@router.get(
    "/leads/{lead_id}/notes",
    response_model=list[NoteOut],
    dependencies=[Depends(require_crm_token)],
)
async def api_list_notes(
    lead_id: int,
    session: AsyncSession = Depends(get_session),
) -> list[NoteOut]:
    lead = await lead_service.get_lead(session, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Лид не найден")
    notes = await lead_service.list_notes(session, lead_id)
    return [NoteOut.model_validate(n) for n in notes]


@router.post(
    "/leads/{lead_id}/notes",
    response_model=NoteOut,
)
async def api_add_note(
    lead_id: int,
    payload: NoteCreate,
    auth: AuthContext = Depends(require_crm_token),
    session: AsyncSession = Depends(get_session),
) -> NoteOut:
    lead = await lead_service.get_lead(session, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Лид не найден")
    note = await lead_service.add_note(
        session,
        lead_id=lead_id,
        body=payload.body,
        author=payload.author or auth.actor,
    )
    return NoteOut.model_validate(note)


@router.post("/chat", response_model=ChatOut, dependencies=[Depends(enforce_chat_limit)])
async def api_chat(payload: ChatIn, session: AsyncSession = Depends(get_session)) -> ChatOut:
    funnel = await funnel_service.ensure_default_funnel(session)
    if payload.lead_id:
        lead = await lead_service.get_lead(session, payload.lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Лид не найден")
    elif payload.telegram_id:
        lead = await lead_service.get_or_create_by_telegram(
            session,
            telegram_id=payload.telegram_id,
            source=payload.source,
            username=payload.telegram_username,
            funnel_id=funnel.id,
        )
    else:
        lead = await lead_service.create_lead(
            session,
            LeadCreate(
                source=payload.source,
                status="qualifying",
                funnel_id=funnel.id,
                stage_slug="qualify",
            ),
        )

    ai = build_ai()
    lead, reply, ready = await lead_service.chat_with_lead(
        session, ai, lead=lead, message=payload.message
    )
    metrics.inc("aifunnel_chat_messages_total", labels={"ready": str(ready).lower()})
    return ChatOut(
        lead_id=lead.id,
        reply=reply,
        status=lead.status,
        ready_for_handoff=ready,
        score=lead.score,
    )
