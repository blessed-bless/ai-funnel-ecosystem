import hmac

from fastapi import Header, HTTPException, status

from aifunnel.config import get_settings


async def require_crm_token(x_crm_token: str | None = Header(default=None)) -> None:
    expected = get_settings().crm_api_token
    provided = x_crm_token or ""
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный CRM-токен")
