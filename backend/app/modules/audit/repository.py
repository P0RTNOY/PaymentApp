"""Firestore repository for audit events."""

from __future__ import annotations

import logging
from typing import Any

import ulid

from app.infra.firestore import collection, set_document, server_timestamp

logger = logging.getLogger(__name__)

AUDIT_EVENTS = "audit_events"


def generate_event_id() -> str:
    return f"ae_{ulid.new().str.lower()}"


async def write_audit_event(event_data: dict[str, Any]) -> str:
    """Write an immutable audit event. Returns the event ID."""
    event_id = event_data.get("eventId") or generate_event_id()
    event_data["eventId"] = event_id
    event_data["createdAt"] = server_timestamp()
    await set_document(AUDIT_EVENTS, event_id, event_data)
    logger.debug(
        "Audit event written",
        extra={
            "eventType": event_data.get("eventType"),
            "entityType": event_data.get("entityType"),
            "entityId": event_data.get("entityId"),
        },
    )
    return event_id


async def write_auth_audit(
    tenant_id: str,
    user_id: str,
    event_type: str,
    *,
    correlation_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> str:
    """Convenience: write an auth-related audit event."""
    return await write_audit_event({
        "tenantId": tenant_id,
        "entityType": "user",
        "entityId": user_id,
        "eventType": event_type,
        "actorType": "user",
        "actorId": user_id,
        "correlationId": correlation_id,
        "payload": payload or {},
    })
