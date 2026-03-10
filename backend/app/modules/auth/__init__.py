"""Domain models for the auth module."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, EmailStr


# ── Enums ────────────────────────────────────────────────────────────────

class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    LOCKED = "locked"


class SessionStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ResetTokenStatus(StrEnum):
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"


# ── User ─────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Input for user registration."""
    email: str
    password: str
    display_name: str | None = None
    phone: str | None = None


class UserRecord(BaseModel):
    """Firestore user document shape."""
    user_id: str = Field(..., alias="userId")
    email: str
    email_lower: str = Field(..., alias="emailLower")
    display_name: str | None = Field(None, alias="displayName")
    phone: str | None = None
    password_hash: str = Field(..., alias="passwordHash")
    password_hash_version: int = Field(1, alias="passwordHashVersion")
    password_changed_at: datetime | None = Field(None, alias="passwordChangedAt")
    google_account_id: str | None = Field(None, alias="googleAccountId")
    phone_verified: bool = Field(False, alias="phoneVerified")
    phone_verified_at: datetime | None = Field(None, alias="phoneVerifiedAt")
    auth_methods: list[str] = Field(default_factory=lambda: ["password"], alias="authMethods")
    status: UserStatus = UserStatus.ACTIVE
    failed_login_count: int = Field(0, alias="failedLoginCount")
    locked_until: datetime | None = Field(None, alias="lockedUntil")
    last_login_at: datetime | None = Field(None, alias="lastLoginAt")
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


# ── Auth Session ─────────────────────────────────────────────────────────

class DeviceInfo(BaseModel):
    """Device/client metadata for session tracking."""
    platform: str | None = None
    app_version: str | None = Field(None, alias="appVersion")
    device_label: str | None = Field(None, alias="deviceLabel")

    model_config = {"populate_by_name": True}


class SessionRecord(BaseModel):
    """Firestore auth_sessions document shape."""
    session_id: str = Field(..., alias="sessionId")
    user_id: str = Field(..., alias="userId")
    tenant_id: str = Field(..., alias="tenantId")
    refresh_token_hash: str = Field(..., alias="refreshTokenHash")
    refresh_token_version: int = Field(1, alias="refreshTokenVersion")
    device_info: DeviceInfo | None = Field(None, alias="deviceInfo")
    ip_address_last_seen: str | None = Field(None, alias="ipAddressLastSeen")
    user_agent: str | None = Field(None, alias="userAgent")
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime | None = Field(None, alias="createdAt")
    last_seen_at: datetime | None = Field(None, alias="lastSeenAt")
    expires_at: datetime | None = Field(None, alias="expiresAt")
    revoked_at: datetime | None = Field(None, alias="revokedAt")
    revoked_reason: str | None = Field(None, alias="revokedReason")

    model_config = {"populate_by_name": True}


# ── Password Reset Token ────────────────────────────────────────────────

class PasswordResetTokenRecord(BaseModel):
    """Firestore password_reset_tokens document shape."""
    token_id: str = Field(..., alias="tokenId")
    user_id: str = Field(..., alias="userId")
    email_lower: str = Field(..., alias="emailLower")
    token_hash: str = Field(..., alias="tokenHash")
    status: ResetTokenStatus = ResetTokenStatus.ACTIVE
    created_at: datetime | None = Field(None, alias="createdAt")
    expires_at: datetime | None = Field(None, alias="expiresAt")
    used_at: datetime | None = Field(None, alias="usedAt")

    model_config = {"populate_by_name": True}


# ── API Request/Response Models ──────────────────────────────────────────

class RegisterRequest(BaseModel):
    """POST /v1/auth/register request body."""
    email: str
    password: str
    display_name: str | None = Field(None, alias="displayName")
    tenant: TenantCreateInput


class TenantCreateInput(BaseModel):
    """Inline tenant creation during registration."""
    name: str
    country_code: str = Field("IL", alias="countryCode")
    timezone: str = "Asia/Jerusalem"
    currency: str = "ILS"

    model_config = {"populate_by_name": True}


class LoginRequest(BaseModel):
    """POST /v1/auth/login request body."""
    email: str
    password: str
    device: DeviceInfo | None = None


class RefreshRequest(BaseModel):
    """POST /v1/auth/refresh request body."""
    refresh_token: str = Field(..., alias="refreshToken")

    model_config = {"populate_by_name": True}


class LogoutRequest(BaseModel):
    """POST /v1/auth/logout request body."""
    refresh_token: str = Field(..., alias="refreshToken")

    model_config = {"populate_by_name": True}


class ForgotPasswordRequest(BaseModel):
    """POST /v1/auth/forgot-password request body."""
    email: str


class ResetPasswordRequest(BaseModel):
    """POST /v1/auth/reset-password request body."""
    token: str
    new_password: str = Field(..., alias="newPassword")

    model_config = {"populate_by_name": True}


class SessionResponse(BaseModel):
    """Token pair returned after login/register."""
    access_token: str = Field(..., alias="accessToken")
    expires_in_sec: int = Field(..., alias="expiresInSec")
    refresh_token: str = Field(..., alias="refreshToken")

    model_config = {"populate_by_name": True}


class UserResponse(BaseModel):
    """Public user profile returned in API responses."""
    user_id: str = Field(..., alias="userId")
    email: str
    display_name: str | None = Field(None, alias="displayName")

    model_config = {"populate_by_name": True}


class TenantContextResponse(BaseModel):
    """Tenant context in session responses."""
    tenant_id: str = Field(..., alias="tenantId")
    name: str
    role: str

    model_config = {"populate_by_name": True}


class RegisterResponse(BaseModel):
    """POST /v1/auth/register response data."""
    user: UserResponse
    tenant: TenantContextResponse
    session: SessionResponse


class LoginResponse(BaseModel):
    """POST /v1/auth/login response data."""
    user: UserResponse
    tenant: TenantContextResponse
    session: SessionResponse


class MeResponse(BaseModel):
    """GET /v1/me response data."""
    user_id: str = Field(..., alias="userId")
    email: str
    display_name: str | None = Field(None, alias="displayName")
    active_tenant: TenantContextResponse = Field(..., alias="activeTenant")

    model_config = {"populate_by_name": True}


class SessionListItem(BaseModel):
    """Session list item for GET /v1/me/sessions."""
    session_id: str = Field(..., alias="sessionId")
    device_info: DeviceInfo | None = Field(None, alias="deviceInfo")
    ip_address_last_seen: str | None = Field(None, alias="ipAddressLastSeen")
    status: str
    created_at: datetime | None = Field(None, alias="createdAt")
    last_seen_at: datetime | None = Field(None, alias="lastSeenAt")

    model_config = {"populate_by_name": True}


# Forward reference fix for RegisterRequest
RegisterRequest.model_rebuild()
