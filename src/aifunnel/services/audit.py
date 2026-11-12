import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.models import AuditEvent


async def record(
    session: AsyncSession,
    *,
    action: str,
    actor: str = "system",
    entity_type: str = "lead",
    entity_id: str | int | None = None,
    payload: dict[str, Any] | None = None,
    commit: bool = True,
) -> None:
    session.add(
        AuditEvent(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=None if entity_id is None else str(entity_id),
            payload=None if payload is None else json.dumps(payload, ensure_ascii=False),
        )
    )
    if commit:
        await session.commit()
