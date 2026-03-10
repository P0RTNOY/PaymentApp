"""Tests for configuration and settings."""

from __future__ import annotations

from app.config import Settings


def test_default_settings():
    """Default settings should have sensible values."""
    s = Settings()
    assert s.environment == "local"
    assert s.api_port == 8000
    assert s.access_token_expire_minutes == 15
    assert s.refresh_token_expire_days == 30
    assert s.login_max_attempts == 5
    assert s.login_lockout_minutes == 15


def test_settings_accepts_env_override(monkeypatch):
    """Settings should pick up APP_ prefixed environment variables."""
    monkeypatch.setenv("APP_ENVIRONMENT", "staging")
    monkeypatch.setenv("APP_API_PORT", "9000")
    s = Settings()
    assert s.environment == "staging"
    assert s.api_port == 9000
