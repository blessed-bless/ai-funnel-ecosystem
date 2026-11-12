from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from aifunnel.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine():
    settings = get_settings()
    return create_async_engine(settings.database_url, echo=False)


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def dispose_engine() -> None:
    """Закрывает пул соединений — иначе aiosqlite ругается после закрытия event loop."""
    await engine.dispose()


def rebind_engine(url: str) -> None:
    """Пересоздаёт engine/sessionmaker — нужно тестам и hot-reload конфига."""
    global engine, SessionLocal
    engine = create_async_engine(url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _sqlite_add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    rows = await conn.execute(text(f"PRAGMA table_info({table})"))
    names = {row[1] for row in rows}
    if column not in names:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


async def apply_lightweight_migrations() -> None:
    """Минимальные миграции для SQLite без alembic на старте."""
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # create_all уже создал таблицы; добираем колонки на старых БД
        try:
            await _sqlite_add_column_if_missing(conn, "leads", "email", "email VARCHAR(160)")
            await _sqlite_add_column_if_missing(conn, "leads", "funnel_id", "funnel_id INTEGER")
            await _sqlite_add_column_if_missing(conn, "leads", "stage_slug", "stage_slug VARCHAR(64)")
            await _sqlite_add_column_if_missing(conn, "leads", "score", "score INTEGER DEFAULT 0")
        except Exception:
            # Новая БД / нет таблицы leads ещё — create_all ниже/выше покрывает
            pass


async def init_db() -> None:
    from aifunnel import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await apply_lightweight_migrations()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
