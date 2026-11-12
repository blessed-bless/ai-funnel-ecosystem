import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from aifunnel.config import Settings

logger = logging.getLogger("aifunnel.webhooks")


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


async def post_webhook(settings: Settings, event: str, payload: dict[str, Any]) -> None:
    url = (settings.webhook_url or "").strip()
    if not url:
        logger.info("webhook skipped (WEBHOOK_URL empty) event=%s", event)
        return

    body_obj = {"event": event, "data": payload}
    body = json.dumps(body_obj, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ai-funnel-ecosystem/webhook",
        "X-Aifunnel-Event": event,
    }
    if settings.webhook_secret:
        headers["X-Aifunnel-Signature"] = sign_payload(settings.webhook_secret, body)

    timeout = httpx.Timeout(settings.webhook_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, content=body, headers=headers)
        if response.status_code >= 400:
            raise RuntimeError(f"webhook HTTP {response.status_code}: {response.text[:300]}")
    logger.info("webhook ok event=%s status=%s", event, response.status_code)
