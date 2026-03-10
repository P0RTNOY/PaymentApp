"""JWT token creation and verification utilities."""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any

import jwt

from app.config import get_settings

logger = logging.getLogger(__name__)


def create_access_token(
    user_id: str,
    session_id: str,
    tenant_id: str,
    *,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Create a short-lived JWT access token.

    Token payload follows the spec:
    ``{ sub, sid, activeTenantId, type, iat, exp }``
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": user_id,
        "sid": session_id,
        "activeTenantId": tenant_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT access token.

    Raises
    ------
    jwt.ExpiredSignatureError
        If the token has expired.
    jwt.InvalidTokenError
        If the token is malformed or invalid.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret_key,
        algorithms=[settings.jwt_algorithm],
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token type is not 'access'")
    return payload


def generate_refresh_token() -> str:
    """Generate a cryptographically secure opaque refresh token."""
    return secrets.token_urlsafe(48)


def generate_reset_token() -> str:
    """Generate a cryptographically secure one-time password reset token."""
    return secrets.token_urlsafe(32)
