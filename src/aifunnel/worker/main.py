import asyncio
import logging
import signal

from aifunnel.config import get_settings
from aifunnel.db import SessionLocal, init_db
from aifunnel.logging_setup import setup_logging
from aifunnel.services import outbox

logger = logging.getLogger("aifunnel.worker")
_stop = asyncio.Event()


def _handle_signal(*_args) -> None:
    _stop.set()


async def _loop() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    await init_db()
    logger.info("worker started")
    while not _stop.is_set():
        async with SessionLocal() as session:
            jobs = await outbox.claim_pending(session, limit=25)
            for job in jobs:
                try:
                    await outbox.process_job(session, job)
                except Exception as exc:
                    await outbox.mark_failed(session, job, str(exc), retry=True)
        try:
            await asyncio.wait_for(_stop.wait(), timeout=2.0)
        except TimeoutError:
            continue
    logger.info("worker stopped")


def run() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _handle_signal())
    try:
        loop.run_until_complete(_loop())
    finally:
        loop.close()


if __name__ == "__main__":
    run()
