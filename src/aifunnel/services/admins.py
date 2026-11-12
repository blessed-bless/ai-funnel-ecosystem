from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aifunnel.config import Settings
from aifunnel.models import AdminUser
from aifunnel.security.passwords import hash_password, verify_password


async def ensure_bootstrap_admin(session: AsyncSession, settings: Settings) -> AdminUser:
    result = await session.execute(select(AdminUser).where(AdminUser.username == settings.admin_username))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = AdminUser(
        username=settings.admin_username,
        password_hash=hash_password(settings.admin_password),
        role="admin",
        is_active=1,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def authenticate(session: AsyncSession, username: str, password: str) -> AdminUser | None:
    result = await session.execute(select(AdminUser).where(AdminUser.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
