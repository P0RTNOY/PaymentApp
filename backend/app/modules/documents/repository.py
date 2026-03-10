"""Firestore repositories for documents and provider configs."""

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

DOCUMENTS = "documents"
PROVIDER_CONFIGS = "provider_configs"


def generate_document_id() -> str:
    return f"doc_{ulid.new().str.lower()}"


def generate_config_id() -> str:
    return f"pc_{ulid.new().str.lower()}"


# ── Provider Configs ────────────────────────────────────────────────────

async def create_provider_config(config_data: dict[str, Any]) -> None:
    """Create a new provider config document."""
    config_data["createdAt"] = server_timestamp()
    config_data["updatedAt"] = server_timestamp()
    await set_document(PROVIDER_CONFIGS, config_data["configId"], config_data)
    logger.info("Created provider config", extra={"configId": config_data["configId"]})


async def get_provider_config(config_id: str) -> dict[str, Any] | None:
    """Fetch provider config by ID."""
    return await get_document(PROVIDER_CONFIGS, config_id)


async def update_provider_config(config_id: str, updates: dict[str, Any]) -> None:
    """Partially update provider config fields."""
    updates["updatedAt"] = server_timestamp()
    await update_document(PROVIDER_CONFIGS, config_id, updates)


async def get_active_provider_config(tenant_id: str, provider_type: str | None = None) -> dict[str, Any] | None:
    """
    Get the active provider config for a tenant.
    If provider_type is None, returns the first active config found.
    """
    coll = collection(PROVIDER_CONFIGS)
    query = coll.where("tenantId", "==", tenant_id).where("isActive", "==", True)
    
    if provider_type:
        query = query.where("providerType", "==", provider_type)
        
    query = query.limit(1)
    
    async for doc in query.stream():
        return doc.to_dict()
    return None


async def list_tenant_provider_configs(tenant_id: str) -> list[dict[str, Any]]:
    """List all provider configs for a tenant."""
    coll = collection(PROVIDER_CONFIGS)
    query = coll.where("tenantId", "==", tenant_id)
    configs = []
    async for doc in query.stream():
        configs.append(doc.to_dict())
    return configs


# ── Documents (Receipts) ───────────────────────────────────────────────

async def create_document(doc_data: dict[str, Any]) -> None:
    """Create a new document record."""
    doc_data["createdAt"] = server_timestamp()
    await set_document(DOCUMENTS, doc_data["documentId"], doc_data)
    logger.info("Created document", extra={"documentId": doc_data["documentId"]})


async def get_document_by_id(document_id: str) -> dict[str, Any] | None:
    """Fetch document by ID."""
    return await get_document(DOCUMENTS, document_id)


async def get_document_by_transaction(tenant_id: str, transaction_id: str) -> dict[str, Any] | None:
    """Fetch the document associated with a specific transaction."""
    coll = collection(DOCUMENTS)
    query = coll.where("tenantId", "==", tenant_id).where("transactionId", "==", transaction_id).limit(1)
    
    async for doc in query.stream():
        return doc.to_dict()
    return None


async def update_document_record(document_id: str, updates: dict[str, Any]) -> None:
    """Partially update document fields."""
    await update_document(DOCUMENTS, document_id, updates)
