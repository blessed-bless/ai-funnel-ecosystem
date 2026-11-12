from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.api.auth import AuthContext, require_crm_or_jwt
from aifunnel.config import Settings, get_settings
from aifunnel.db import get_session
from aifunnel.observability import metrics
from aifunnel.security.jwt_tokens import create_access_token
from aifunnel.services import admins as admin_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_minutes: int


class MeOut(BaseModel):
    actor: str
    method: str
    role: str


@router.post("/login", response_model=LoginOut)
async def login(
    payload: LoginIn,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> LoginOut:
    user = await admin_service.authenticate(session, payload.username, payload.password)
    if not user:
        metrics.inc("aifunnel_auth_failures_total", labels={"reason": "bad_credentials"})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    token = create_access_token(settings, subject=user.username, role=user.role)
    metrics.inc("aifunnel_auth_logins_total")
    return LoginOut(access_token=token, expires_minutes=settings.jwt_expire_minutes)


@router.get("/me", response_model=MeOut)
async def me(auth: AuthContext = Depends(require_crm_or_jwt)) -> MeOut:
    return MeOut(actor=auth.actor, method=auth.method, role=auth.role)
