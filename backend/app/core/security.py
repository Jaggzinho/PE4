from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

from pe3_qc_app.core.context import Session


@dataclass(frozen=True)
class JwtSettings:
    secret: str
    algorithm: str = "HS256"
    access_token_minutes: int = 12 * 60


def create_access_token(session: Session, *, settings: JwtSettings) -> str:
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(minutes=int(settings.access_token_minutes))
    payload = {
        "sub": str(session.user_id),
        "username": session.username,
        "role_name": session.role_name,
        "permissions": dict(session.permissions or {}),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.secret, algorithm=settings.algorithm)


def decode_access_token(token: str, *, settings: JwtSettings) -> dict:
    return jwt.decode(token, settings.secret, algorithms=[settings.algorithm])


__all__ = ["JwtSettings", "create_access_token", "decode_access_token"]
