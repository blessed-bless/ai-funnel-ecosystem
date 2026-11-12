from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.api.auth import require_crm_token
from aifunnel.db import get_session
from aifunnel.schemas import FunnelCreate, FunnelOut
from aifunnel.services import funnels as funnel_service

router = APIRouter(prefix="/api/funnels", tags=["funnels"], dependencies=[Depends(require_crm_token)])


@router.get("", response_model=list[FunnelOut])
async def list_funnels(session: AsyncSession = Depends(get_session)) -> list[FunnelOut]:
    await funnel_service.ensure_default_funnel(session)
    items = await funnel_service.list_funnels(session)
    return [FunnelOut.model_validate(item) for item in items]


@router.post("", response_model=FunnelOut)
async def create_funnel(
    payload: FunnelCreate,
    session: AsyncSession = Depends(get_session),
) -> FunnelOut:
    existing = await funnel_service.get_by_slug(session, payload.slug)
    if existing:
        raise HTTPException(status_code=409, detail="Воронка с таким slug уже есть")
    funnel = await funnel_service.create_funnel(session, payload)
    return FunnelOut.model_validate(funnel)
