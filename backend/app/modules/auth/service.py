"""Auth service — registration, login, refresh, logout, password reset."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from app.config import get_settings
from app.config.logging import request_id_var
from app.infra.auth.password import hash_password, verify_password, needs_rehash, PASSWORD_HASH_VERSION
from app.infra.auth.tokens import (
    create_access_token,
    generate_refresh_token,
    generate_reset_token,
)
from app.modules.auth.repository import (
    find_user_by_email,
    get_user_by_id,
    create_user,
    update_user,
    generate_user_id,
    generate_session_id,
    generate_reset_token_id,
    hash_token,
    create_session,
    get_session_by_id,
    update_session,
    revoke_session,
    revoke_all_user_sessions,
    list_user_sessions,
    create_reset_token,
    get_reset_token,
    mark_reset_token_used,
)
from app.modules.tenants.repository import (
    create_tenant,
    get_tenant_by_id,
    create_membership,
    get_membership,
    generate_tenant_id,
)
from app.modules.tenants import MembershipRole, DEFAULT_ROLE_PERMISSIONS
from app.modules.audit.repository import write_auth_audit

logger = logging.getLogger(__name__)


class AuthError(Exception):
    """Base class for auth-related errors."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ── Registration ─────────────────────────────────────────────────────────

async def register(
    email: str,
    password: str,
    display_name: str | None,
    tenant_name: str,
    country_code: str = "IL",
    tenant_timezone: str = "Asia/Jerusalem",
    currency: str = "ILS",
    device_info: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Register a new user and bootstrap their tenant.

    Returns dict with ``user``, ``tenant``, ``session`` keys.
    """
    settings = get_settings()
    email_lower = email.strip().lower()

    # Check email uniqueness
    existing = await find_user_by_email(email_lower)
    if existing:
        raise AuthError("auth.email_already_exists", "Email already registered.", 409)

    # Create user
    user_id = generate_user_id()
    pw_hash = hash_password(password)
    user_data = {
        "userId": user_id,
        "email": email.strip(),
        "emailLower": email_lower,
        "displayName": display_name,
        "phone": None,
        "passwordHash": pw_hash,
        "passwordHashVersion": PASSWORD_HASH_VERSION,
        "passwordChangedAt": None,
        "googleAccountId": None,
        "phoneVerified": False,
        "phoneVerifiedAt": None,
        "authMethods": ["password"],
        "status": "active",
        "failedLoginCount": 0,
        "lockedUntil": None,
        "lastLoginAt": None,
    }
    await create_user(user_data)

    # Create tenant
    tenant_id = generate_tenant_id()
    tenant_data = {
        "tenantId": tenant_id,
        "name": tenant_name,
        "legalName": None,
        "countryCode": country_code,
        "timezone": tenant_timezone,
        "currency": currency,
        "status": "active",
        "branding": {"logoUrl": None, "primaryColor": None, "senderName": None},
        "defaultDocumentProviderId": None,
    }
    await create_tenant(tenant_data)

    # Create owner membership
    role = MembershipRole.OWNER
    membership_data = {
        "tenantId": tenant_id,
        "userId": user_id,
        "role": role.value,
        "permissions": DEFAULT_ROLE_PERMISSIONS[role],
        "status": "active",
    }
    await create_membership(membership_data)

    # Create session
    session = await _create_session(
        user_id=user_id,
        tenant_id=tenant_id,
        device_info=device_info,
        ip_address=ip_address,
    )

    # Audit
    await write_auth_audit(tenant_id, user_id, "auth.registered")

    return {
        "user": {
            "userId": user_id,
            "email": email.strip(),
            "displayName": display_name,
        },
        "tenant": {
            "tenantId": tenant_id,
            "name": tenant_name,
            "role": role.value,
        },
        "session": session,
    }


# ── Login ────────────────────────────────────────────────────────────────

async def login(
    email: str,
    password: str,
    device_info: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Authenticate user with email and password.

    Returns dict with ``user``, ``tenant``, ``session`` keys.
    """
    settings = get_settings()
    email_lower = email.strip().lower()

    user = await find_user_by_email(email_lower)
    if not user:
        raise AuthError("auth.invalid_credentials", "Invalid email or password.", 401)

    user_id = user["userId"]

    # Check lock
    if user.get("lockedUntil"):
        lock_until = user["lockedUntil"]
        if isinstance(lock_until, datetime) and lock_until > datetime.now(timezone.utc):
            await write_auth_audit(user.get("tenantId", "unknown"), user_id, "auth.login_failed", payload={"reason": "locked"})
            raise AuthError("auth.account_locked", "Account is temporarily locked.", 423)

    # Verify password
    if not verify_password(password, user["passwordHash"]):
        failed_count = user.get("failedLoginCount", 0) + 1
        updates: dict[str, Any] = {"failedLoginCount": failed_count}
        if failed_count >= settings.login_max_attempts:
            updates["lockedUntil"] = datetime.now(timezone.utc) + timedelta(minutes=settings.login_lockout_minutes)
            updates["failedLoginCount"] = 0
        await update_user(user_id, updates)
        await write_auth_audit(user.get("tenantId", "unknown"), user_id, "auth.login_failed", payload={"failedCount": failed_count})
        raise AuthError("auth.invalid_credentials", "Invalid email or password.", 401)

    # Check if status is not active
    if user.get("status") != "active":
        raise AuthError("auth.account_suspended", "Account is suspended.", 403)

    # Success — reset failed count and update last login
    updates_success: dict[str, Any] = {
        "failedLoginCount": 0,
        "lockedUntil": None,
        "lastLoginAt": datetime.now(timezone.utc),
    }

    # Rehash if needed
    if needs_rehash(user["passwordHash"]):
        updates_success["passwordHash"] = hash_password(password)
        updates_success["passwordHashVersion"] = PASSWORD_HASH_VERSION
    await update_user(user_id, updates_success)

    # Find tenant membership — use first active membership
    from app.modules.tenants.repository import list_user_memberships
    memberships = await list_user_memberships(user_id)
    if not memberships:
        raise AuthError("auth.no_tenant", "User has no active tenant.", 403)

    membership = memberships[0]
    tenant_id = membership["tenantId"]
    tenant = await get_tenant_by_id(tenant_id)

    # Create session
    session = await _create_session(
        user_id=user_id,
        tenant_id=tenant_id,
        device_info=device_info,
        ip_address=ip_address,
    )

    await write_auth_audit(tenant_id, user_id, "auth.login_succeeded")

    return {
        "user": {
            "userId": user_id,
            "email": user["email"],
            "displayName": user.get("displayName"),
        },
        "tenant": {
            "tenantId": tenant_id,
            "name": tenant["name"] if tenant else "Unknown",
            "role": membership["role"],
        },
        "session": session,
    }


# ── Refresh ──────────────────────────────────────────────────────────────

async def refresh_token(refresh_token_value: str) -> dict[str, Any]:
    """Rotate refresh token and issue new access token.

    Returns dict with ``accessToken``, ``expiresInSec``, ``refreshToken``.
    """
    settings = get_settings()
    token_hash = hash_token(refresh_token_value)

    # Find session by searching — in production this would be indexed differently
    # For MVP we lookup by hash
    from app.infra.firestore import collection
    coll = collection("auth_sessions")
    query = coll.where("refreshTokenHash", "==", token_hash).where("status", "==", "active").limit(1)
    session_data = None
    async for doc_snap in query.stream():
        session_data = doc_snap.to_dict()
        break

    if not session_data:
        raise AuthError("auth.invalid_session", "Invalid or expired refresh token.", 401)

    # Check expiry
    expires_at = session_data.get("expiresAt")
    if expires_at and isinstance(expires_at, datetime) and expires_at < datetime.now(timezone.utc):
        await revoke_session(session_data["sessionId"], "expired")
        raise AuthError("auth.invalid_session", "Session has expired.", 401)

    # Rotate refresh token
    new_refresh = generate_refresh_token()
    new_hash = hash_token(new_refresh)
    new_version = session_data.get("refreshTokenVersion", 1) + 1

    await update_session(session_data["sessionId"], {
        "refreshTokenHash": new_hash,
        "refreshTokenVersion": new_version,
        "lastSeenAt": datetime.now(timezone.utc),
    })

    # Issue new access token
    access_token = create_access_token(
        user_id=session_data["userId"],
        session_id=session_data["sessionId"],
        tenant_id=session_data["tenantId"],
    )

    await write_auth_audit(
        session_data["tenantId"],
        session_data["userId"],
        "auth.refresh_succeeded",
    )

    return {
        "accessToken": access_token,
        "expiresInSec": settings.access_token_expire_minutes * 60,
        "refreshToken": new_refresh,
    }


# ── Logout ───────────────────────────────────────────────────────────────

async def logout(refresh_token_value: str) -> bool:
    """Revoke the session associated with the given refresh token."""
    token_hash = hash_token(refresh_token_value)

    from app.infra.firestore import collection
    coll = collection("auth_sessions")
    query = coll.where("refreshTokenHash", "==", token_hash).limit(1)
    async for doc_snap in query.stream():
        session_data = doc_snap.to_dict()
        await revoke_session(doc_snap.id, "logout")
        await write_auth_audit(
            session_data.get("tenantId", "unknown"),
            session_data.get("userId", "unknown"),
            "auth.logout",
        )
        return True
    return True  # idempotent — always succeed


async def logout_all(user_id: str, tenant_id: str) -> int:
    """Revoke all sessions for the current user."""
    count = await revoke_all_user_sessions(user_id, "logout_all")
    await write_auth_audit(tenant_id, user_id, "auth.logout_all")
    return count


# ── Password Reset ──────────────────────────────────────────────────────

async def request_password_reset(email: str) -> bool:
    """Request a password reset. Always returns True to prevent enumeration."""
    email_lower = email.strip().lower()
    user = await find_user_by_email(email_lower)

    if user:
        token = generate_reset_token()
        token_id = generate_reset_token_id()
        settings = get_settings()

        token_data = {
            "tokenId": token_id,
            "userId": user["userId"],
            "emailLower": email_lower,
            "tokenHash": hash_token(token),
            "status": "active",
            "expiresAt": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        await create_reset_token(token_data)

        await write_auth_audit(
            "system", user["userId"],
            "auth.password_reset_requested",
        )

        # TODO: Send email with reset link containing token_id and token
        logger.info(
            "Password reset token created",
            extra={"userId": user["userId"], "tokenId": token_id},
        )
    else:
        # Log but don't reveal non-existence
        await write_auth_audit("system", "unknown", "auth.password_reset_requested", payload={"email": email_lower})

    return True


async def reset_password(token_id: str, raw_token: str, new_password: str) -> bool:
    """Reset password using a valid reset token."""
    token_data = await get_reset_token(token_id)

    if not token_data:
        raise AuthError("auth.invalid_reset_token", "Invalid or expired reset token.", 400)

    if token_data.get("status") != "active":
        raise AuthError("auth.invalid_reset_token", "Reset token already used.", 400)

    # Check expiry
    expires_at = token_data.get("expiresAt")
    if expires_at and isinstance(expires_at, datetime) and expires_at < datetime.now(timezone.utc):
        raise AuthError("auth.invalid_reset_token", "Reset token has expired.", 400)

    # Verify token hash
    if hash_token(raw_token) != token_data["tokenHash"]:
        raise AuthError("auth.invalid_reset_token", "Invalid reset token.", 400)

    # Update password
    user_id = token_data["userId"]
    new_hash = hash_password(new_password)
    await update_user(user_id, {
        "passwordHash": new_hash,
        "passwordHashVersion": PASSWORD_HASH_VERSION,
        "passwordChangedAt": datetime.now(timezone.utc),
    })

    # Mark token used
    await mark_reset_token_used(token_id)

    # Revoke all sessions
    await revoke_all_user_sessions(user_id, "password_reset")

    await write_auth_audit("system", user_id, "auth.password_reset_completed")

    return True


# ── Get current user info ────────────────────────────────────────────────

async def get_me(user_id: str, tenant_id: str) -> dict[str, Any]:
    """Get current user profile with active tenant context."""
    user = await get_user_by_id(user_id)
    if not user:
        raise AuthError("auth.user_not_found", "User not found.", 404)

    membership = await get_membership(tenant_id, user_id)
    tenant = await get_tenant_by_id(tenant_id)

    return {
        "userId": user["userId"],
        "email": user["email"],
        "displayName": user.get("displayName"),
        "activeTenant": {
            "tenantId": tenant_id,
            "name": tenant["name"] if tenant else "Unknown",
            "role": membership["role"] if membership else "unknown",
        },
    }


async def get_sessions(user_id: str) -> list[dict[str, Any]]:
    """List all sessions for the current user."""
    sessions = await list_user_sessions(user_id)
    return [
        {
            "sessionId": s.get("sessionId"),
            "deviceInfo": s.get("deviceInfo"),
            "ipAddressLastSeen": s.get("ipAddressLastSeen"),
            "status": s.get("status"),
            "createdAt": s.get("createdAt"),
            "lastSeenAt": s.get("lastSeenAt"),
        }
        for s in sessions
    ]


async def delete_session(user_id: str, session_id: str, tenant_id: str) -> bool:
    """Revoke a specific session belonging to the current user."""
    session = await get_session_by_id(session_id)
    if not session or session.get("userId") != user_id:
        raise AuthError("auth.session_not_found", "Session not found.", 404)

    await revoke_session(session_id, "user_revoked")
    await write_auth_audit(tenant_id, user_id, "auth.session_revoked", payload={"sessionId": session_id})
    return True


# ── Internal helpers ─────────────────────────────────────────────────────

async def _create_session(
    user_id: str,
    tenant_id: str,
    device_info: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Create an auth session and return the token pair."""
    settings = get_settings()
    session_id = generate_session_id()
    raw_refresh = generate_refresh_token()
    refresh_hash = hash_token(raw_refresh)

    session_data = {
        "sessionId": session_id,
        "userId": user_id,
        "tenantId": tenant_id,
        "refreshTokenHash": refresh_hash,
        "refreshTokenVersion": 1,
        "deviceInfo": device_info,
        "ipAddressLastSeen": ip_address,
        "userAgent": None,
        "status": "active",
        "expiresAt": datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        "revokedAt": None,
        "revokedReason": None,
    }
    await create_session(session_data)

    access_token = create_access_token(
        user_id=user_id,
        session_id=session_id,
        tenant_id=tenant_id,
    )

    return {
        "accessToken": access_token,
        "expiresInSec": settings.access_token_expire_minutes * 60,
        "refreshToken": raw_refresh,
    }
