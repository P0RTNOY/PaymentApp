"""Auth API router — all authentication and session endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.config.logging import request_id_var
from app.modules.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    LogoutRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.config.rate_limit import limiter
from app.modules.auth.service import (
    AuthError,
    register as auth_register,
    login as auth_login,
    refresh_token as auth_refresh,
    logout as auth_logout,
    logout_all as auth_logout_all,
    request_password_reset,
    reset_password,
    get_me,
    get_sessions,
    delete_session,
)
from app.modules.auth.dependencies import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/auth", tags=["auth"])
me_router = APIRouter(prefix="/v1", tags=["me"])


def _req_id() -> str:
    return request_id_var.get() or "unknown"


def _wrap(data: dict, status_code: int = 200) -> JSONResponse:
    """Wrap response in standard API envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"data": data, "meta": {"requestId": _req_id()}},
    )


def _err(e: AuthError) -> JSONResponse:
    """Wrap AuthError into standard error envelope."""
    return JSONResponse(
        status_code=e.status_code,
        content={
            "error": {"code": e.code, "message": e.message},
            "meta": {"requestId": _req_id()},
        },
    )


# ── POST /v1/auth/register ──────────────────────────────────────────────

@router.post("/register")
async def register_endpoint(body: RegisterRequest, request: Request) -> JSONResponse:
    """Register a new user and bootstrap their tenant."""
    try:
        result = await auth_register(
            email=body.email,
            password=body.password,
            display_name=body.display_name,
            tenant_name=body.tenant.name,
            country_code=body.tenant.country_code,
            tenant_timezone=body.tenant.timezone,
            currency=body.tenant.currency,
            ip_address=request.client.host if request.client else None,
        )
        return _wrap(result, 201)
    except AuthError as e:
        return _err(e)


# ── POST /v1/auth/login ─────────────────────────────────────────────────

@router.post("/login")
@limiter.limit("5/minute")
async def login_endpoint(body: LoginRequest, request: Request) -> JSONResponse:
    """Authenticate with email and password."""
    try:
        device = body.device.model_dump(by_alias=True) if body.device else None
        result = await auth_login(
            email=body.email,
            password=body.password,
            device_info=device,
            ip_address=request.client.host if request.client else None,
        )
        return _wrap(result)
    except AuthError as e:
        return _err(e)


# ── POST /v1/auth/refresh ───────────────────────────────────────────────

@router.post("/refresh")
async def refresh_endpoint(body: RefreshRequest) -> JSONResponse:
    """Rotate refresh token and get new access token."""
    try:
        result = await auth_refresh(body.refresh_token)
        return _wrap(result)
    except AuthError as e:
        return _err(e)


# ── POST /v1/auth/logout ────────────────────────────────────────────────

@router.post("/logout")
async def logout_endpoint(body: LogoutRequest) -> JSONResponse:
    """Revoke the current session."""
    await auth_logout(body.refresh_token)
    return _wrap({"loggedOut": True})


# ── POST /v1/auth/logout-all ────────────────────────────────────────────

@router.post("/logout-all")
async def logout_all_endpoint(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JSONResponse:
    """Revoke all sessions for the current user."""
    count = await auth_logout_all(current_user.user_id, current_user.tenant_id)
    return _wrap({"loggedOut": True, "sessionsRevoked": count})


# ── POST /v1/auth/forgot-password ───────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password_endpoint(body: ForgotPasswordRequest) -> JSONResponse:
    """Request a password reset email."""
    await request_password_reset(body.email)
    return _wrap({"accepted": True})


# ── POST /v1/auth/reset-password ────────────────────────────────────────

@router.post("/reset-password")
async def reset_password_endpoint(body: ResetPasswordRequest) -> JSONResponse:
    """Reset password using a valid reset token."""
    try:
        # Token format expected: "{tokenId}:{rawToken}"
        parts = body.token.split(":", 1)
        if len(parts) != 2:
            raise AuthError("auth.invalid_reset_token", "Malformed reset token.", 400)
        token_id, raw_token = parts

        await reset_password(token_id, raw_token, body.new_password)
        return _wrap({"passwordReset": True, "sessionsRevoked": True})
    except AuthError as e:
        return _err(e)


# ── GET /v1/me ───────────────────────────────────────────────────────────

@me_router.get("/me")
async def me_endpoint(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JSONResponse:
    """Get current user profile and active tenant context."""
    try:
        result = await get_me(current_user.user_id, current_user.tenant_id)
        return _wrap(result)
    except AuthError as e:
        return _err(e)


# ── GET /v1/me/sessions ─────────────────────────────────────────────────

@me_router.get("/me/sessions")
async def me_sessions_endpoint(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JSONResponse:
    """List all sessions for the current user."""
    sessions = await get_sessions(current_user.user_id)
    return _wrap(sessions)


# ── DELETE /v1/me/sessions/{sessionId} ──────────────────────────────────

@me_router.delete("/me/sessions/{session_id}")
async def delete_session_endpoint(
    session_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JSONResponse:
    """Revoke a specific session."""
    try:
        await delete_session(current_user.user_id, session_id, current_user.tenant_id)
        return _wrap({"revoked": True})
    except AuthError as e:
        return _err(e)
