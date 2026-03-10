"""Firestore client singleton and tenant-scoped query helpers."""

from __future__ import annotations

import logging
from typing import Any

from google.cloud import firestore  # type: ignore[attr-defined]

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: firestore.AsyncClient | None = None


def get_firestore_client() -> firestore.AsyncClient:
    """Return a cached asynchronous Firestore client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = firestore.AsyncClient(
            project=settings.project_id,
            database=settings.firestore_database,
        )
        logger.info("Firestore async client initialised", extra={
            "database": settings.firestore_database,
        })
    return _client


# ── Collection references ────────────────────────────────────────────────

def collection(name: str) -> firestore.AsyncCollectionReference:
    """Return a top-level collection reference."""
    return get_firestore_client().collection(name)


def document(collection_name: str, doc_id: str) -> firestore.AsyncDocumentReference:
    """Return a document reference by collection and ID."""
    return collection(collection_name).document(doc_id)


# ── Tenant-scoped query helpers ──────────────────────────────────────────

def tenant_query(
    collection_name: str,
    tenant_id: str,
) -> firestore.AsyncQuery:
    """Return a query scoped to a specific tenant."""
    return collection(collection_name).where("tenantId", "==", tenant_id)


async def get_document(collection_name: str, doc_id: str) -> dict[str, Any] | None:
    """Fetch a single document by ID. Returns None if not found."""
    snap = await document(collection_name, doc_id).get()
    return snap.to_dict() if snap.exists else None


async def set_document(
    collection_name: str,
    doc_id: str,
    data: dict[str, Any],
    merge: bool = False,
) -> None:
    """Create or overwrite a document."""
    await document(collection_name, doc_id).set(data, merge=merge)


async def update_document(
    collection_name: str,
    doc_id: str,
    updates: dict[str, Any],
) -> None:
    """Partially update an existing document."""
    await document(collection_name, doc_id).update(updates)


async def delete_document(collection_name: str, doc_id: str) -> None:
    """Delete a document by ID."""
    await document(collection_name, doc_id).delete()


def server_timestamp() -> Any:
    """Return a Firestore server timestamp sentinel."""
    return firestore.SERVER_TIMESTAMP
