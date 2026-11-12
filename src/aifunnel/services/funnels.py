from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from aifunnel.cache import funnel_id_cache
from aifunnel.models import Funnel, FunnelStage
from aifunnel.schemas import FunnelCreate

DEFAULT_STAGES = [
    ("awareness", "Интерес", 10),
    ("qualify", "Квалификация", 20),
    ("ready", "Готов к менеджеру", 30),
    ("handed", "Передан", 40),
]


async def ensure_default_funnel(session: AsyncSession) -> Funnel:
    cached_id = funnel_id_cache.get("default")
    if cached_id is not None:
        funnel = await session.get(
            Funnel,
            cached_id,
            options=(selectinload(Funnel.stages),),
        )
        if funnel is not None:
            return funnel

    result = await session.execute(
        select(Funnel).options(selectinload(Funnel.stages)).where(Funnel.slug == "default")
    )
    funnel = result.scalar_one_or_none()
    if funnel:
        funnel_id_cache.set("default", funnel.id)
        return funnel

    funnel = Funnel(
        slug="default",
        title="Основная воронка",
        description="Лендинг → бот → CRM",
        is_active=1,
    )
    session.add(funnel)
    await session.flush()
    for slug, title, position in DEFAULT_STAGES:
        session.add(FunnelStage(funnel_id=funnel.id, slug=slug, title=title, position=position))
    await session.commit()
    result = await session.execute(
        select(Funnel).options(selectinload(Funnel.stages)).where(Funnel.id == funnel.id)
    )
    funnel = result.scalar_one()
    funnel_id_cache.set("default", funnel.id)
    return funnel


async def list_funnels(session: AsyncSession) -> list[Funnel]:
    result = await session.execute(select(Funnel).options(selectinload(Funnel.stages)).order_by(Funnel.id))
    return list(result.scalars().all())


async def get_by_slug(session: AsyncSession, slug: str) -> Funnel | None:
    result = await session.execute(
        select(Funnel).options(selectinload(Funnel.stages)).where(Funnel.slug == slug)
    )
    return result.scalar_one_or_none()


async def create_funnel(session: AsyncSession, payload: FunnelCreate) -> Funnel:
    funnel = Funnel(slug=payload.slug, title=payload.title, description=payload.description, is_active=1)
    session.add(funnel)
    await session.flush()
    for slug, title, position in DEFAULT_STAGES:
        session.add(FunnelStage(funnel_id=funnel.id, slug=slug, title=title, position=position))
    await session.commit()
    result = await session.execute(
        select(Funnel).options(selectinload(Funnel.stages)).where(Funnel.id == funnel.id)
    )
    return result.scalar_one()
