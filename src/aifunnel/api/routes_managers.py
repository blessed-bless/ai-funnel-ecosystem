from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.api.auth import require_crm_token
from aifunnel.db import get_session
from aifunnel.schemas import ManagerOut, ManagerUpsert
from aifunnel.services import workspace as workspace_service

router = APIRouter(prefix="/api/managers", tags=["managers"], dependencies=[Depends(require_crm_token)])


@router.get("", response_model=list[ManagerOut])
async def list_managers(session: AsyncSession = Depends(get_session)) -> list[ManagerOut]:
    ws = await workspace_service.ensure_default_workspace(session)
    items = await workspace_service.list_managers(session, ws.id)
    return [ManagerOut.model_validate(i) for i in items]


@router.post("", response_model=ManagerOut)
async def upsert_manager(
    payload: ManagerUpsert,
    session: AsyncSession = Depends(get_session),
) -> ManagerOut:
    ws = await workspace_service.ensure_default_workspace(session)
    try:
        manager = await workspace_service.upsert_manager(
            session,
            workspace_id=ws.id,
            name=payload.name,
            telegram_chat_id=payload.telegram_chat_id,
            manager_id=payload.manager_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ManagerOut.model_validate(manager)
