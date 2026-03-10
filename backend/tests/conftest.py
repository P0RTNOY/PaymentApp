"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    """Create a fresh FastAPI application instance for testing."""
    return create_app()


@pytest.fixture
async def client(app):
    """Async HTTP test client for the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
