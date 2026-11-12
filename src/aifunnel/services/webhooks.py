import hashlib
import hmac
import json
import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.config import Settings
from aifunnel.models import WebhookDelivery
from aifunnel.reliability import with_retries

logger = logging.getLogger("aifunnel.webhooks")


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def _store_delivery(
    session: AsyncSession | None,
    *,
    event: str,
    target: str,
    status_code: int,
    success: bool,
    payload: dict[str, Any],
    response_body: str | None = None,
) -> None:
    if session is None:
        return
    session.add(
        WebhookDelivery(
            event=event,
            target=target[:255],
            status_code=status_code,
            success=1 if success else 0,
            response_body=(response_body or "")[:2000] or None,
            payload=json.dumps(payload, ensure_ascii=False),
        )
    )
    await session.commit()


async def post_webhook(
    settings: Settings,
    event: str,
    payload: dict[str, Any],
    *,
    session: AsyncSession | None = None,
) -> None:
    url = (settings.webhook_url or "").strip()
    body_obj = {"event": event, "data": payload}
    body = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")

    if not url:
        # Не заглушка «просто лог»: фиксируем локальную доставку в БД
        await _store_delivery(
            session,
            event=event,
            target="local://log",
            status_code=0,
            success=True,
            payload=body_obj,
            response_body="stored locally (WEBHOOK_URL empty)",
        )
        logger.info("webhook local-store event=%s lead_id=%s", event, payload.get("lead_id"))
        return

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ai-funnel-ecosystem/webhook",
        "X-Aifunnel-Event": event,
    }
    if settings.webhook_secret:
        headers["X-Aifunnel-Signature"] = sign_payload(settings.webhook_secret, body)

    timeout = httpx.Timeout(settings.webhook_timeout_seconds)

    async def _send() -> httpx.Response:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, content=body, headers=headers)
            if response.status_code >= 500:
                raise RuntimeError(f"webhook HTTP {response.status_code}")
            return response

    try:
        response = await with_retries(_send, attempts=3, base_delay=0.35, label="webhook")
    except Exception as exc:
        await _store_delivery(
            session,
            event=event,
            target=url,
            status_code=0,
            success=False,
            payload=body_obj,
            response_body=str(exc)[:500],
        )
        raise

    ok = response.status_code < 400
    await _store_delivery(
        session,
        event=event,
        target=url,
        status_code=response.status_code,
        success=ok,
        payload=body_obj,
        response_body=response.text[:500],
    )
    if not ok:
        raise RuntimeError(f"webhook HTTP {response.status_code}: {response.text[:300]}")
    logger.info("webhook ok event=%s status=%s", event, response.status_code)
