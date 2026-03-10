"""Pub/Sub publish helper for domain event fan-out."""

from __future__ import annotations
from datetime import datetime, timezone

import json
import logging
import os
from concurrent.futures import Future
from typing import Any

from google.cloud import pubsub_v1
from pydantic import BaseModel, Field

from app.config import get_settings

logger = logging.getLogger(__name__)

_publisher: pubsub_v1.PublisherClient | None = None


def get_publisher_client() -> pubsub_v1.PublisherClient:
    """Return a cached Pub/Sub publisher client."""
    global _publisher
    if _publisher is None:
        _publisher = pubsub_v1.PublisherClient()
        logger.info("Pub/Sub publisher client initialised")
    return _publisher


# Placeholder for future message schema
class DomainEvent(BaseModel):
    event_type: str
    tenant_id: str
    data: dict[str, Any]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


async def publish_event(
    topic_id: str,
    event_type: str,
    tenant_id: str,
    data: dict[str, Any],
    ordering_key: str | None = None,
) -> str | None:
    """
    Publish an event to a Pub/Sub topic.
    Returns the message ID if successful, or None if publishing fails.
    """
    publisher = get_publisher_client() # Renamed from get_publisher to match existing function
    if not publisher:
        # Mock mode
        logger.info(
            f"MOCK PUB/SUB: Event '{event_type}' on '{topic_id}' for tenant '{tenant_id}'."
        )
        return "mock-msg-id"
        
    project_id = get_settings().project_id # Changed from gcp_project_id to project_id to match existing settings
    topic_path = publisher.topic_path(project_id, topic_id)
    
    event = DomainEvent(event_type=event_type, tenant_id=tenant_id, data=data)
    payload_json = event.model_dump_json()
    payload_bytes = payload_json.encode("utf-8")
    
    # Custom attributes used for routing or filtering
    attributes = {
        "eventType": event_type,
        "tenantId": tenant_id,
        "schemaVersion": "1.0",
    }
    
    try:
        future: Future = publisher.publish(
            topic_path,
            payload_bytes,
            ordering_key=ordering_key or "",
            **attributes
        )
        msg_id: str = future.result(timeout=5.0)  # Wait up to 5s for ack
        logger.debug(f"Published event {event_type} to {topic_id} (msgId: {msg_id})")
        return msg_id
    except Exception as e:
        logger.error(f"Failed to publish event {event_type} to {topic_id}: {e}")
        return None


async def verify_pubsub_jwt(token: str) -> bool:
    """
    Verify the OIDC token sent by GCP Pub/Sub push subscriptions.
    In a real app, this uses google-auth to verify the JWT signature and audience.
    """
    # For MVP / test environments, if it's our test token, allow it.
    if token == "mock-pubsub-token":
        return True
    
    # TODO: Implement google.oauth2.id_token.verify_oauth2_token
    # against the exact audience configured in the push subscription.
    logger.warning("PubSub JWT verification is mocked for MVP.")
    return False
