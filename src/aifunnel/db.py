from collections.abc import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from aifunnel.config import get_settings


class Base(DeclarativeBase):
    pass


def _configure_sqlite(sync_conn) -> None:
    # Скорость и параллельные читатели на одном файле
    sync_conn.execute(text("PRAGMA journal_mode=WAL"))
    sync_conn.execute(text("PRAGMA synchronous=NORMAL"))
    sync_conn.execute(text("PRAGMA temp_store=MEMORY"))
    sync_conn.execute(text("PRAGMA foreign_keys=ON"))


def _make_engine(url: str | None = None):
    settings = get_settings()
    db_url = url or settings.database_url
    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    eng = create_async_engine(db_url, echo=False, connect_args=connect_args)
    if db_url.startswith("sqlite"):

        @event.listens_for(eng.sync_engine, "connect")
        def _on_connect(dbapi_conn, _connection_record):  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return eng


engine = _make_engine()
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def dispose_engine() -> None:
    """Закрывает пул соединений — иначе aiosqlite ругается после закрытия event loop."""
    await engine.dispose()


def rebind_engine(url: str) -> None:
    """Пересоздаёт engine/sessionmaker — нужно тестам и hot-reload конфига."""
    global engine, SessionLocal
    engine = _make_engine(url)
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
        try:
            await _sqlite_add_column_if_missing(conn, "leads", "email", "email VARCHAR(160)")
            await _sqlite_add_column_if_missing(conn, "leads", "funnel_id", "funnel_id INTEGER")
            await _sqlite_add_column_if_missing(conn, "leads", "stage_slug", "stage_slug VARCHAR(64)")
            await _sqlite_add_column_if_missing(conn, "leads", "score", "score INTEGER DEFAULT 0")
            await _sqlite_add_column_if_missing(conn, "leads", "tags", "tags VARCHAR(255)")
            await _sqlite_add_column_if_missing(
                conn, "leads", "phone_normalized", "phone_normalized VARCHAR(32)"
            )
            await _sqlite_add_column_if_missing(conn, "leads", "workspace_id", "workspace_id INTEGER")
            await _sqlite_add_column_if_missing(
                conn, "leads", "assigned_manager_id", "assigned_manager_id INTEGER"
            )
            await _sqlite_add_column_if_missing(conn, "leads", "deleted_at", "deleted_at DATETIME")
            await _sqlite_add_column_if_missing(conn, "funnels", "workspace_id", "workspace_id INTEGER")
        except Exception:
            pass


async def init_db() -> None:
    from aifunnel import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await apply_lightweight_migrations()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
