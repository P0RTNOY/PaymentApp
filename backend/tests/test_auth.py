"""Tests for auth API endpoints using mocked Firestore."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────

def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _make_user(
    user_id: str = "u_test123",
    email: str = "test@example.com",
    password_hash: str = "",
    status: str = "active",
    failed_login_count: int = 0,
    locked_until=None,
) -> dict:
    return {
        "userId": user_id,
        "email": email,
        "emailLower": email.lower(),
        "displayName": "Test User",
        "phone": None,
        "passwordHash": password_hash,
        "passwordHashVersion": 1,
        "passwordChangedAt": None,
        "googleAccountId": None,
        "phoneVerified": False,
        "phoneVerifiedAt": None,
        "authMethods": ["password"],
        "status": status,
        "failedLoginCount": failed_login_count,
        "lockedUntil": locked_until,
        "lastLoginAt": None,
        "createdAt": datetime.now(timezone.utc),
    }


def _make_membership(
    tenant_id: str = "t_test123",
    user_id: str = "u_test123",
    role: str = "owner",
) -> dict:
    return {
        "tenantId": tenant_id,
        "userId": user_id,
        "role": role,
        "permissions": ["transactions.read", "documents.issue"],
        "status": "active",
        "createdAt": datetime.now(timezone.utc),
        "updatedAt": datetime.now(timezone.utc),
    }


def _make_tenant(tenant_id: str = "t_test123", name: str = "Test Co") -> dict:
    return {
        "tenantId": tenant_id,
        "name": name,
        "legalName": None,
        "countryCode": "IL",
        "timezone": "Asia/Jerusalem",
        "currency": "ILS",
        "status": "active",
        "branding": {},
        "createdAt": datetime.now(timezone.utc),
    }


def _make_session(
    session_id: str = "s_test123",
    user_id: str = "u_test123",
    tenant_id: str = "t_test123",
    refresh_hash: str = "",
    status: str = "active",
) -> dict:
    return {
        "sessionId": session_id,
        "userId": user_id,
        "tenantId": tenant_id,
        "refreshTokenHash": refresh_hash,
        "refreshTokenVersion": 1,
        "deviceInfo": None,
        "ipAddressLastSeen": None,
        "status": status,
        "createdAt": datetime.now(timezone.utc),
        "lastSeenAt": datetime.now(timezone.utc),
        "expiresAt": datetime.now(timezone.utc) + timedelta(days=30),
        "revokedAt": None,
    }


# ── Registration Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.auth.service.write_auth_audit", new_callable=AsyncMock)
@patch("app.modules.auth.service.create_membership", new_callable=AsyncMock)
@patch("app.modules.auth.service.create_tenant", new_callable=AsyncMock)
@patch("app.modules.auth.service.create_user", new_callable=AsyncMock)
@patch("app.modules.auth.service.create_session", new_callable=AsyncMock)
@patch("app.modules.auth.service.find_user_by_email", new_callable=AsyncMock)
async def test_register_success(
    mock_find, mock_create_session, mock_create_user,
    mock_create_tenant, mock_create_membership, mock_audit,
    client,
):
    """POST /v1/auth/register should create user, tenant, and session."""
    mock_find.return_value = None  # email not taken

    response = await client.post("/v1/auth/register", json={
        "email": "new@example.com",
        "password": "StrongP@ss123",
        "displayName": "New User",
        "tenant": {
            "name": "My Business",
            "countryCode": "IL",
            "timezone": "Asia/Jerusalem",
            "currency": "ILS",
        },
    })

    assert response.status_code == 201
    data = response.json()
    assert "data" in data
    assert "meta" in data
    assert data["data"]["user"]["email"] == "new@example.com"
    assert data["data"]["tenant"]["name"] == "My Business"
    assert data["data"]["tenant"]["role"] == "owner"
    assert "accessToken" in data["data"]["session"]
    assert "refreshToken" in data["data"]["session"]
    assert "expiresInSec" in data["data"]["session"]


@pytest.mark.asyncio
@patch("app.modules.auth.service.find_user_by_email", new_callable=AsyncMock)
async def test_register_duplicate_email(mock_find, client):
    """POST /v1/auth/register with existing email should return 409."""
    mock_find.return_value = _make_user()

    response = await client.post("/v1/auth/register", json={
        "email": "test@example.com",
        "password": "StrongP@ss123",
        "tenant": {"name": "Test"},
    })

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "auth.email_already_exists"


# ── Login Tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.auth.service.write_auth_audit", new_callable=AsyncMock)
@patch("app.modules.auth.service.create_session", new_callable=AsyncMock)
@patch("app.modules.auth.service.get_tenant_by_id", new_callable=AsyncMock)
@patch("app.modules.tenants.repository.list_user_memberships", new_callable=AsyncMock)
@patch("app.modules.auth.service.update_user", new_callable=AsyncMock)
@patch("app.modules.auth.service.find_user_by_email", new_callable=AsyncMock)
async def test_login_success(
    mock_find, mock_update, mock_memberships, mock_tenant,
    mock_create_session, mock_audit, client,
):
    """POST /v1/auth/login with valid credentials should return tokens."""
    from app.infra.auth.password import hash_password
    pw_hash = hash_password("correct-password")
    mock_find.return_value = _make_user(password_hash=pw_hash)
    mock_memberships.return_value = [_make_membership()]
    mock_tenant.return_value = _make_tenant()

    response = await client.post("/v1/auth/login", json={
        "email": "test@example.com",
        "password": "correct-password",
    })

    assert response.status_code == 200
    data = response.json()["data"]
    assert "session" in data
    assert data["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
@patch("app.modules.auth.service.write_auth_audit", new_callable=AsyncMock)
@patch("app.modules.auth.service.update_user", new_callable=AsyncMock)
@patch("app.modules.auth.service.find_user_by_email", new_callable=AsyncMock)
async def test_login_wrong_password(mock_find, mock_update, mock_audit, client):
    """POST /v1/auth/login with wrong password should return 401."""
    from app.infra.auth.password import hash_password
    pw_hash = hash_password("correct-password")
    mock_find.return_value = _make_user(password_hash=pw_hash)

    response = await client.post("/v1/auth/login", json={
        "email": "test@example.com",
        "password": "wrong-password",
    })

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "auth.invalid_credentials"


@pytest.mark.asyncio
@patch("app.modules.auth.service.find_user_by_email", new_callable=AsyncMock)
async def test_login_nonexistent_email(mock_find, client):
    """POST /v1/auth/login with unknown email should return 401."""
    mock_find.return_value = None

    response = await client.post("/v1/auth/login", json={
        "email": "nobody@example.com",
        "password": "any-password",
    })

    assert response.status_code == 401


@pytest.mark.asyncio
@patch("app.modules.auth.service.write_auth_audit", new_callable=AsyncMock)
@patch("app.modules.auth.service.find_user_by_email", new_callable=AsyncMock)
async def test_login_locked_account(mock_find, mock_audit, client):
    """POST /v1/auth/login for locked account should return 423."""
    mock_find.return_value = _make_user(
        locked_until=datetime.now(timezone.utc) + timedelta(minutes=10),
    )

    response = await client.post("/v1/auth/login", json={
        "email": "test@example.com",
        "password": "any-password",
    })

    assert response.status_code == 423
    assert response.json()["error"]["code"] == "auth.account_locked"


# ── Refresh Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.auth.service.write_auth_audit", new_callable=AsyncMock)
@patch("app.modules.auth.service.update_session", new_callable=AsyncMock)
async def test_refresh_success(mock_update, mock_audit, client):
    """POST /v1/auth/refresh with valid token should return new tokens."""
    raw_token = "test-refresh-token"
    token_hash = _hash(raw_token)
    session = _make_session(refresh_hash=token_hash)

    # Mock Firestore query for session lookup
    mock_doc = MagicMock()
    mock_doc.to_dict.return_value = session

    async def mock_stream():
        yield mock_doc

    with patch("app.infra.firestore.collection") as mock_coll:
        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.stream = mock_stream
        mock_coll.return_value = mock_query

        response = await client.post("/v1/auth/refresh", json={
            "refreshToken": raw_token,
        })

    assert response.status_code == 200
    data = response.json()["data"]
    assert "accessToken" in data
    assert "refreshToken" in data
    assert data["refreshToken"] != raw_token  # rotated


# ── Logout Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_logout_returns_success(client):
    """POST /v1/auth/logout should always return success (idempotent)."""
    mock_doc = MagicMock()
    mock_doc.id = "s_test123"
    mock_doc.to_dict.return_value = _make_session()

    async def mock_stream():
        yield mock_doc

    with patch("app.infra.firestore.collection") as mock_coll, \
         patch("app.modules.auth.service.revoke_session", new_callable=AsyncMock), \
         patch("app.modules.auth.service.write_auth_audit", new_callable=AsyncMock):
        mock_query = MagicMock()
        mock_query.where.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.stream = mock_stream
        mock_coll.return_value = mock_query

        response = await client.post("/v1/auth/logout", json={
            "refreshToken": "some-token",
        })

    assert response.status_code == 200
    assert response.json()["data"]["loggedOut"] is True


# ── Forgot Password Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.auth.service.write_auth_audit", new_callable=AsyncMock)
@patch("app.modules.auth.service.create_reset_token", new_callable=AsyncMock)
@patch("app.modules.auth.service.find_user_by_email", new_callable=AsyncMock)
async def test_forgot_password_always_accepted(mock_find, mock_create, mock_audit, client):
    """POST /v1/auth/forgot-password should always return accepted."""
    mock_find.return_value = None  # user doesn't exist

    response = await client.post("/v1/auth/forgot-password", json={
        "email": "nobody@example.com",
    })

    assert response.status_code == 200
    assert response.json()["data"]["accepted"] is True


# ── Protected Endpoint Tests ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_without_token_returns_401(client):
    """GET /v1/me without Authorization header should return 401."""
    response = await client.get("/v1/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_with_invalid_token_returns_401(client):
    """GET /v1/me with invalid token should return 401."""
    response = await client.get("/v1/me", headers={
        "Authorization": "Bearer invalid.token.here",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
@patch("app.modules.auth.dependencies.get_membership", new_callable=AsyncMock)
async def test_me_with_valid_token(mock_membership, client):
    """GET /v1/me with valid token should return user profile."""
    from app.infra.auth.tokens import create_access_token

    mock_membership.return_value = _make_membership()

    access_token = create_access_token("u_test123", "s_test123", "t_test123")

    with patch("app.modules.auth.service.get_user_by_id", new_callable=AsyncMock) as mock_user, \
         patch("app.modules.auth.service.get_membership", new_callable=AsyncMock) as mock_mem, \
         patch("app.modules.auth.service.get_tenant_by_id", new_callable=AsyncMock) as mock_tenant:
        mock_user.return_value = _make_user()
        mock_mem.return_value = _make_membership()
        mock_tenant.return_value = _make_tenant()

        response = await client.get("/v1/me", headers={
            "Authorization": f"Bearer {access_token}",
        })

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["userId"] == "u_test123"
    assert data["email"] == "test@example.com"
    assert "activeTenant" in data
