"""Health and readiness check endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check() -> dict:
    """Liveness probe — always returns OK if the process is running."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness_check() -> dict:
    """Readiness probe — confirms the service can accept traffic.

    For MVP this is identical to health. In the future it can verify
    Firestore connectivity, Secret Manager access, etc.
    """
    return {
        "status": "ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
