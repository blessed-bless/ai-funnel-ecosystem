from fastapi import APIRouter
from sqlalchemy import text

from aifunnel import __version__
from aifunnel.ai import build_ai
from aifunnel.ai.resilient import ResilientAIProvider
from aifunnel.config import get_settings
from aifunnel import db as dbmod
from aifunnel.schemas import HealthOut, ReadyOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health() -> HealthOut:
    settings = get_settings()
    return HealthOut(status="ok", version=__version__, env=settings.app_env)


@router.get("/ready", response_model=ReadyOut)
async def ready() -> ReadyOut:
    settings = get_settings()
    db_status = "ok"
    try:
        async with dbmod.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    ai = build_ai()
    circuit = ai.circuit_state if isinstance(ai, ResilientAIProvider) else "n/a"
    status = "ok" if db_status == "ok" or not settings.ready_require_db else "degraded"
    if db_status == "error" and settings.ready_require_db:
        status = "not_ready"
    return ReadyOut(status=status, database=db_status, ai_circuit=circuit)
