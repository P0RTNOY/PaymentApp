"""FastAPI dependencies for authentication and authorization."""

from __future__ import annotations

import logging
from typing import Any, Annotated

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config.logging import tenant_id_var, user_id_var
from app.infra.auth.tokens import decode_access_token
from app.modules.tenants.repository import get_membership

logger = logging.getLogger(__name__)

# ── Bearer scheme ────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)


# ── Current user ─────────────────────────────────────────────────────────

class CurrentUser:
    """Authenticated user context available in request handlers."""

    def __init__(
        self,
        user_id: str,
        session_id: str,
        tenant_id: str,
        role: str | None = None,
        permissions: list[str] | None = None,
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.role = role
        self.permissions = permissions or []

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> CurrentUser:
    """Dependency: extract and validate the JWT access token.

    Also populates context vars for structured logging.
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail={
            "code": "auth.missing_token",
            "message": "Authorization header is required.",
        })

    try:
        payload = decode_access_token(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={
            "code": "auth.token_expired",
            "message": "Access token has expired.",
        })
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail={
            "code": "auth.invalid_token",
            "message": "Invalid access token.",
        })

    user_id = payload["sub"]
    session_id = payload["sid"]
    tenant_id = payload["activeTenantId"]

    # Set context vars for logging
    tenant_id_var.set(tenant_id)
    user_id_var.set(user_id)

    # Load current membership (role/permissions)
    membership = await get_membership(tenant_id, user_id)
    if not membership or membership.get("status") != "active":
        raise HTTPException(status_code=403, detail={
            "code": "auth.no_active_membership",
            "message": "No active membership for this tenant.",
        })

    return CurrentUser(
        user_id=user_id,
        session_id=session_id,
        tenant_id=tenant_id,
        role=membership.get("role"),
        permissions=membership.get("permissions", []),
    )


# ── Role/permission guards ──────────────────────────────────────────────

def require_role(*allowed_roles: str):
    """Dependency factory: require one of the specified roles."""

    async def _check(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail={
                "code": "auth.insufficient_role",
                "message": f"Requires one of: {', '.join(allowed_roles)}",
            })
        return current_user

    return _check


def require_permission(permission: str):
    """Dependency factory: require a specific permission."""

    async def _check(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if not current_user.has_permission(permission):
            raise HTTPException(status_code=403, detail={
                "code": "auth.insufficient_permission",
                "message": f"Missing required permission: {permission}",
            })
        return current_user

    return _check
