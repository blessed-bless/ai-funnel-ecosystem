from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.api.routes_funnels import router as funnels_router
from aifunnel.api.routes_health import router as health_router
from aifunnel.api.routes_leads import router as leads_router
from aifunnel.config import get_settings
from aifunnel.db import SessionLocal, get_session, init_db
from aifunnel.logging_setup import setup_logging
from aifunnel.schemas import LeadUpdate
from aifunnel.security import RequestIdMiddleware, SecurityHeadersMiddleware
from aifunnel.services import funnels as funnel_service
from aifunnel.services import leads as lead_service

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "web" / "templates"
STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    await init_db()
    async with SessionLocal() as session:
        await funnel_service.ensure_default_funnel(session)
    yield


app = FastAPI(title="AI Funnel Ecosystem", version="0.2.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.include_router(health_router)
app.include_router(leads_router)
app.include_router(funnels_router)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request) -> HTMLResponse:
    cfg = get_settings()
    if cfg.telegram_bot_username:
        bot_link = f"https://t.me/{cfg.telegram_bot_username.lstrip('@')}?start=landing"
    else:
        bot_link = "#"
    return templates.TemplateResponse(
        request,
        "landing.html",
        {
            "app_name": cfg.app_name,
            "bot_link": bot_link,
            "api_public_url": cfg.api_public_url,
        },
    )


@app.get("/crm", response_class=HTMLResponse)
async def crm_page(request: Request, session: AsyncSession = Depends(get_session)) -> HTMLResponse:
    items = await lead_service.list_leads(session)
    stats = await lead_service.stats(session)
    return templates.TemplateResponse(
        request,
        "crm.html",
        {
            "app_name": get_settings().app_name,
            "leads": items,
            "stats": stats,
        },
    )


@app.post("/crm/leads/{lead_id}/status")
async def crm_set_status(
    lead_id: int,
    status: str = Form(...),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    lead = await lead_service.get_lead(session, lead_id)
    if lead:
        await lead_service.update_lead(session, lead, LeadUpdate(status=status, stage_slug=status))
    return RedirectResponse(url="/crm", status_code=303)


def run() -> None:
    cfg = get_settings()
    setup_logging(cfg.log_level)
    uvicorn.run(
        "aifunnel.api.app:app",
        host=cfg.api_host,
        port=cfg.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
