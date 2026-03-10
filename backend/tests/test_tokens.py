"""Tests for JWT token utilities."""

from __future__ import annotations

import time

import pytest
import jwt as pyjwt

from app.infra.auth.tokens import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    generate_reset_token,
)


def test_create_and_decode_access_token():
    """Roundtrip: create an access token and decode it."""
    token = create_access_token(
        user_id="u_123",
        session_id="s_456",
        tenant_id="t_789",
    )
    payload = decode_access_token(token)
    assert payload["sub"] == "u_123"
    assert payload["sid"] == "s_456"
    assert payload["activeTenantId"] == "t_789"
    assert payload["type"] == "access"


def test_access_token_contains_expiry():
    """Access token should have iat and exp claims."""
    token = create_access_token("u_1", "s_1", "t_1")
    payload = decode_access_token(token)
    assert "iat" in payload
    assert "exp" in payload
    assert payload["exp"] > payload["iat"]


def test_decode_rejects_invalid_token():
    """Decoding garbage should raise."""
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_access_token("not.a.token")


def test_refresh_token_is_unique():
    """Each refresh token should be unique."""
    t1 = generate_refresh_token()
    t2 = generate_refresh_token()
    assert t1 != t2
    assert len(t1) > 30


def test_reset_token_is_unique():
    """Each reset token should be unique."""
    t1 = generate_reset_token()
    t2 = generate_reset_token()
    assert t1 != t2
    assert len(t1) > 20
