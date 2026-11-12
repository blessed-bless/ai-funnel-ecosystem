import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.config import get_settings
from aifunnel.models import OutboxJob
from aifunnel.services import webhooks

logger = logging.getLogger("aifunnel.outbox")


async def enqueue(
    session: AsyncSession,
    *,
    kind: str,
    payload: dict[str, Any],
) -> OutboxJob:
    job = OutboxJob(kind=kind, payload=json.dumps(payload, ensure_ascii=False), status="pending")
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def claim_pending(session: AsyncSession, limit: int = 20) -> list[OutboxJob]:
    now = datetime.now(timezone.utc)
    base = (
        select(OutboxJob)
        .where(OutboxJob.status == "pending", OutboxJob.available_at <= now)
        .order_by(OutboxJob.id.asc())
        .limit(limit)
    )
    try:
        result = await session.execute(base.with_for_update(skip_locked=True))
    except Exception:
        # SQLite и часть драйверов не умеют SKIP LOCKED — обычный select
        result = await session.execute(base)
    jobs = list(result.scalars().all())
    for job in jobs:
        job.status = "processing"
        job.attempts += 1
    await session.commit()
    return jobs


async def mark_done(session: AsyncSession, job: OutboxJob) -> None:
    job.status = "done"
    job.last_error = None
    await session.commit()


async def mark_failed(session: AsyncSession, job: OutboxJob, error: str, *, retry: bool = True) -> None:
    job.last_error = error[:2000]
    if retry and job.attempts < 5:
        # exponential backoff
        delay = min(300, 2 ** job.attempts)
        job.status = "pending"
        job.available_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
    else:
        job.status = "failed"
    await session.commit()
    logger.error("outbox job_id=%s kind=%s status=%s err=%s", job.id, job.kind, job.status, error)


async def process_job(session: AsyncSession, job: OutboxJob) -> None:
    data = json.loads(job.payload)
    settings = get_settings()
    if job.kind == "notify_ready_lead":
        await webhooks.post_webhook(settings, "lead.ready", data, session=session)
        await mark_done(session, job)
        return
    await mark_failed(session, job, f"unknown kind: {job.kind}", retry=False)
