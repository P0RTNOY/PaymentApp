"""Tests for health endpoints."""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    """GET /health should return status ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_returns_ready(client):
    """GET /ready should return status ready."""
    response = await client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_request_id_header_generated(client):
    """Response should include X-Request-Id header."""
    response = await client.get("/health")
    assert "x-request-id" in response.headers


@pytest.mark.asyncio
async def test_request_id_header_echoed(client):
    """When client sends X-Request-Id, it should be echoed back."""
    custom_id = "test-req-123"
    response = await client.get("/health", headers={"X-Request-Id": custom_id})
    assert response.headers["x-request-id"] == custom_id
