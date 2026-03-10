"""Domain models for the audit module."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    PROVIDER = "provider"


class AuditEventRecord(BaseModel):
    """Firestore audit_events/{eventId} document shape.

    Immutable append-only audit stream.
    """
    event_id: str = Field(..., alias="eventId")
    tenant_id: str = Field(..., alias="tenantId")
    entity_type: str = Field(..., alias="entityType")
    entity_id: str = Field(..., alias="entityId")
    event_type: str = Field(..., alias="eventType")
    actor_type: ActorType = Field(ActorType.SYSTEM, alias="actorType")
    actor_id: str = Field("system", alias="actorId")
    correlation_id: str | None = Field(None, alias="correlationId")
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}
