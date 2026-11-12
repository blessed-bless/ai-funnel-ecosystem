from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.cache import TTLCache
from aifunnel.models import Manager, Workspace

_workspace_cache: TTLCache[int] = TTLCache(ttl_seconds=120.0)


async def ensure_default_workspace(session: AsyncSession) -> Workspace:
    cached = _workspace_cache.get("default")
    if cached is not None:
        ws = await session.get(Workspace, cached)
        if ws is not None:
            return ws

    result = await session.execute(select(Workspace).where(Workspace.slug == "default"))
    ws = result.scalar_one_or_none()
    if ws:
        _workspace_cache.set("default", ws.id)
        return ws

    ws = Workspace(slug="default", title="Основной workspace", is_active=1)
    session.add(ws)
    await session.commit()
    await session.refresh(ws)
    _workspace_cache.set("default", ws.id)
    return ws


async def ensure_default_manager(session: AsyncSession, workspace_id: int) -> Manager:
    result = await session.execute(
        select(Manager).where(Manager.workspace_id == workspace_id, Manager.name == "Default")
    )
    manager = result.scalar_one_or_none()
    if manager:
        return manager
    manager = Manager(workspace_id=workspace_id, name="Default", is_active=1)
    session.add(manager)
    await session.commit()
    await session.refresh(manager)
    return manager


async def list_managers(session: AsyncSession, workspace_id: int) -> list[Manager]:
    result = await session.execute(
        select(Manager).where(Manager.workspace_id == workspace_id).order_by(Manager.id)
    )
    return list(result.scalars().all())


async def upsert_manager(
    session: AsyncSession,
    *,
    workspace_id: int,
    name: str,
    telegram_chat_id: str | None = None,
    manager_id: int | None = None,
) -> Manager:
    if manager_id:
        manager = await session.get(Manager, manager_id)
        if not manager:
            raise ValueError("manager not found")
        manager.name = name
        manager.telegram_chat_id = telegram_chat_id
    else:
        manager = Manager(
            workspace_id=workspace_id,
            name=name,
            telegram_chat_id=telegram_chat_id,
            is_active=1,
        )
        session.add(manager)
    await session.commit()
    await session.refresh(manager)
    return manager
