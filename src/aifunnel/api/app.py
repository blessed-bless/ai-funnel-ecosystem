from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.ai import build_ai
from aifunnel.config import get_settings
from aifunnel.db import get_session, init_db
from aifunnel.api.auth import require_crm_token
from aifunnel.schemas import ChatIn, ChatOut, FunnelHitIn, LeadCreate, LeadOut, LeadUpdate
from aifunnel.services import leads as lead_service

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="AI Funnel Ecosystem", version="0.1.0", lifespan=lifespan)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/funnel/hit", response_model=LeadOut)
async def funnel_hit(
    payload: FunnelHitIn,
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    source = payload.source
    if payload.utm_campaign:
        source = f"{source}:{payload.utm_campaign}"
    lead = await lead_service.create_lead(session, LeadCreate(source=source, status="new"))
    return LeadOut.model_validate(lead)


@app.get("/api/leads", response_model=list[LeadOut], dependencies=[Depends(require_crm_token)])
async def api_list_leads(session: AsyncSession = Depends(get_session)) -> list[LeadOut]:
    items = await lead_service.list_leads(session)
    return [LeadOut.model_validate(item) for item in items]


@app.post("/api/leads", response_model=LeadOut, dependencies=[Depends(require_crm_token)])
async def api_create_lead(
    payload: LeadCreate,
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    lead = await lead_service.create_lead(session, payload)
    return LeadOut.model_validate(lead)


@app.get("/api/leads/{lead_id}", response_model=LeadOut, dependencies=[Depends(require_crm_token)])
async def api_get_lead(lead_id: int, session: AsyncSession = Depends(get_session)) -> LeadOut:
    lead = await lead_service.get_lead(session, lead_id)
    if not lead:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Лид не найден")
    return LeadOut.model_validate(lead)


@app.patch("/api/leads/{lead_id}", response_model=LeadOut, dependencies=[Depends(require_crm_token)])
async def api_patch_lead(
    lead_id: int,
    payload: LeadUpdate,
    session: AsyncSession = Depends(get_session),
) -> LeadOut:
    lead = await lead_service.get_lead(session, lead_id)
    if not lead:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Лид не найден")
    lead = await lead_service.update_lead(session, lead, payload)
    return LeadOut.model_validate(lead)


@app.post("/api/chat", response_model=ChatOut)
async def api_chat(payload: ChatIn, session: AsyncSession = Depends(get_session)) -> ChatOut:
    if payload.lead_id:
        lead = await lead_service.get_lead(session, payload.lead_id)
        if not lead:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Лид не найден")
    elif payload.telegram_id:
        lead = await lead_service.get_or_create_by_telegram(
            session,
            telegram_id=payload.telegram_id,
            source=payload.source,
            username=payload.telegram_username,
        )
    else:
        lead = await lead_service.create_lead(
            session,
            LeadCreate(source=payload.source, status="qualifying"),
        )

    ai = build_ai()
    lead, reply, ready = await lead_service.chat_with_lead(
        session, ai, lead=lead, message=payload.message
    )
    return ChatOut(lead_id=lead.id, reply=reply, status=lead.status, ready_for_handoff=ready)


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    settings = get_settings()
    if settings.telegram_bot_username:
        bot_link = f"https://t.me/{settings.telegram_bot_username.lstrip('@')}?start=landing"
    else:
        bot_link = "#"
    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "app_name": settings.app_name,
            "bot_link": bot_link,
            "api_public_url": settings.api_public_url,
        },
    )


@app.get("/crm", response_class=HTMLResponse)
async def crm_page(request: Request, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    items = await lead_service.list_leads(session)
    return templates.TemplateResponse(
        request,
        "crm.html",
        {"app_name": get_settings().app_name, "leads": items},
    )


@app.post("/crm/leads/{lead_id}/status")
async def crm_set_status(
    lead_id: int,
    status: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    lead = await lead_service.get_lead(session, lead_id)
    if lead:
        await lead_service.update_lead(session, lead, LeadUpdate(status=status))
    return RedirectResponse(url="/crm", status_code=303)


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "aifunnel.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
