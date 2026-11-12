import jwt
from fastapi import Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.config import Settings, get_settings
from aifunnel.db import get_session
from aifunnel.security.jwt_tokens import create_access_token, decode_access_token
from aifunnel.services import admins as admin_service


class CrmLoginRequired(Exception):
    """HTML CRM требует логин — ловится exception handler'ом."""


async def require_crm_page(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> str:
    if not settings.crm_protect_html:
        return "open"
    token = request.cookies.get(settings.crm_cookie_name)
    if not token:
        raise CrmLoginRequired()
    try:
        payload = decode_access_token(settings, token)
    except jwt.PyJWTError as exc:
        raise CrmLoginRequired() from exc
    subject = str(payload.get("sub") or "")
    if not subject:
        raise CrmLoginRequired()
    return subject


async def crm_login_submit(
    username: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    user = await admin_service.authenticate(session, username.strip(), password)
    if not user:
        return RedirectResponse(url="/crm/login?error=1", status_code=303)
    token = create_access_token(settings, subject=user.username, role=user.role)
    response = RedirectResponse(url="/crm", status_code=303)
    response.set_cookie(
        key=settings.crm_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )
    return response


def crm_logout(settings: Settings = Depends(get_settings)) -> RedirectResponse:
    response = RedirectResponse(url="/crm/login", status_code=303)
    response.delete_cookie(settings.crm_cookie_name, path="/")
    return response
