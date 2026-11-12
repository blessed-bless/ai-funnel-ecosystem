from datetime import datetime, timedelta, timezone

import jwt

from aifunnel.config import Settings


def create_access_token(settings: Settings, *, subject: str, role: str = "admin") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(settings: Settings, token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
