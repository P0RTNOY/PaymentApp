"""Firestore repository for tenants and memberships."""

from __future__ import annotations

import logging
from typing import Any

import ulid

from app.infra.firestore import (
    collection,
    get_document,
    set_document,
    update_document,
    server_timestamp,
)

logger = logging.getLogger(__name__)

TENANTS = "tenants"
TENANT_MEMBERSHIPS = "tenant_memberships"


def generate_tenant_id() -> str:
    return f"t_{ulid.new().str.lower()}"


# ── Tenant operations ───────────────────────────────────────────────────

async def create_tenant(tenant_data: dict[str, Any]) -> None:
    """Create a new tenant document."""
    tenant_data["createdAt"] = server_timestamp()
    tenant_data["updatedAt"] = server_timestamp()
    await set_document(TENANTS, tenant_data["tenantId"], tenant_data)
    logger.info("Created tenant", extra={"tenantId": tenant_data["tenantId"]})


async def get_tenant_by_id(tenant_id: str) -> dict[str, Any] | None:
    """Fetch tenant document by ID."""
    return await get_document(TENANTS, tenant_id)


async def update_tenant(tenant_id: str, updates: dict[str, Any]) -> None:
    """Partially update tenant fields."""
    updates["updatedAt"] = server_timestamp()
    await update_document(TENANTS, tenant_id, updates)


# ── Membership operations ───────────────────────────────────────────────

def membership_doc_id(tenant_id: str, user_id: str) -> str:
    """Build the composite document ID for a membership."""
    return f"{tenant_id}_{user_id}"


async def create_membership(membership_data: dict[str, Any]) -> None:
    """Create a tenant membership (role binding)."""
    doc_id = membership_doc_id(
        membership_data["tenantId"],
        membership_data["userId"],
    )
    membership_data["createdAt"] = server_timestamp()
    membership_data["updatedAt"] = server_timestamp()
    await set_document(TENANT_MEMBERSHIPS, doc_id, membership_data)
    logger.info(
        "Created membership",
        extra={
            "tenantId": membership_data["tenantId"],
            "userId": membership_data["userId"],
            "role": membership_data["role"],
        },
    )


async def get_membership(tenant_id: str, user_id: str) -> dict[str, Any] | None:
    """Fetch membership by tenant + user."""
    doc_id = membership_doc_id(tenant_id, user_id)
    return await get_document(TENANT_MEMBERSHIPS, doc_id)


async def list_user_memberships(user_id: str) -> list[dict[str, Any]]:
    """List all tenant memberships for a user."""
    coll = collection(TENANT_MEMBERSHIPS)
    query = coll.where("userId", "==", user_id).where("status", "==", "active")
    memberships = []
    async for doc_snap in query.stream():
        memberships.append(doc_snap.to_dict())
    return memberships


async def update_membership(
    tenant_id: str,
    user_id: str,
    updates: dict[str, Any],
) -> None:
    """Partially update membership fields."""
    doc_id = membership_doc_id(tenant_id, user_id)
    updates["updatedAt"] = server_timestamp()
    await update_document(TENANT_MEMBERSHIPS, doc_id, updates)
