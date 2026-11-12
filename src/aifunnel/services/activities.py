import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.models import LeadActivity


async def add_activity(
    session: AsyncSession,
    *,
    lead_id: int,
    kind: str,
    message: str,
    actor: str = "system",
    meta: dict[str, Any] | None = None,
    commit: bool = False,
) -> LeadActivity:
    row = LeadActivity(
        lead_id=lead_id,
        kind=kind,
        actor=actor,
        message=message,
        meta_json=None if meta is None else json.dumps(meta, ensure_ascii=False),
    )
    session.add(row)
    if commit:
        await session.commit()
        await session.refresh(row)
    return row


async def list_activities(
    session: AsyncSession,
    lead_id: int,
    *,
    limit: int = 100,
) -> list[LeadActivity]:
    result = await session.execute(
        select(LeadActivity)
        .where(LeadActivity.lead_id == lead_id)
        .order_by(LeadActivity.id.desc())
        .limit(min(max(limit, 1), 300))
    )
    return list(result.scalars().all())
