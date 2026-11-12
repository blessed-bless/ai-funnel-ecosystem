import hmac
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from aifunnel.config import Settings, get_settings
from aifunnel.security.jwt_tokens import decode_access_token

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    actor: str
    method: str
    role: str = "admin"


async def require_crm_or_jwt(
    x_crm_token: str | None = Header(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> AuthContext:
    expected = settings.crm_api_token
    provided = x_crm_token or ""
    if provided and hmac.compare_digest(provided, expected):
        return AuthContext(actor="crm-token", method="token", role="admin")

    if credentials and credentials.scheme.lower() == "bearer":
        try:
            payload = decode_access_token(settings, credentials.credentials)
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный или просроченный JWT",
            ) from exc
        subject = str(payload.get("sub") or "")
        role = str(payload.get("role") or "admin")
        if not subject:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пустой subject в JWT")
        return AuthContext(actor=subject, method="jwt", role=role)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Нужен X-CRM-Token или Authorization: Bearer <jwt>",
    )


# Совместимость со старыми импортами
async def require_crm_token(
    auth: AuthContext = Depends(require_crm_or_jwt),
) -> AuthContext:
    return auth
