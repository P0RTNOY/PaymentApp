"""Firestore repository for transactions."""

from __future__ import annotations

import logging
from typing import Any

import ulid
from google.cloud.firestore_v1 import Client

from app.infra.firestore import (
    collection,
    get_document,
    set_document,
    update_document,
    server_timestamp,
    get_firestore_client,
)

logger = logging.getLogger(__name__)

TRANSACTIONS = "transactions"


def generate_transaction_id() -> str:
    return f"txn_{ulid.new().str.lower()}"


async def create_transaction(transaction_data: dict[str, Any]) -> None:
    """Create a new transaction document."""
    transaction_data["createdAt"] = server_timestamp()
    transaction_data["updatedAt"] = server_timestamp()
    await set_document(TRANSACTIONS, transaction_data["transactionId"], transaction_data)
    logger.info("Created transaction", extra={"transactionId": transaction_data["transactionId"]})


async def get_transaction(transaction_id: str) -> dict[str, Any] | None:
    """Fetch transaction document by ID."""
    return await get_document(TRANSACTIONS, transaction_id)


async def update_transaction(transaction_id: str, updates: dict[str, Any]) -> None:
    """Partially update transaction fields."""
    updates["updatedAt"] = server_timestamp()
    await update_document(TRANSACTIONS, transaction_id, updates)


async def find_transaction_by_idempotency_key(tenant_id: str, idempotency_key: str) -> dict[str, Any] | None:
    """Find a transaction by tenant and idempotency key to prevent duplicates."""
    coll = collection(TRANSACTIONS)
    query = coll.where("tenantId", "==", tenant_id).where("idempotencyKey", "==", idempotency_key).limit(1)
    
    async for doc in query.stream():
        return doc.to_dict()
    return None


async def list_tenant_transactions(
    tenant_id: str, 
    limit: int = 50, 
    cursor: str | None = None
) -> tuple[list[dict[str, Any]], str | None]:
    """
    List transactions for a tenant with cursor-based pagination.
    Returns (items, next_cursor).
    """
    coll = collection(TRANSACTIONS)
    query = coll.where("tenantId", "==", tenant_id).order_by("createdAt", direction="DESCENDING")
    
    if cursor:
        client: Client = await get_firestore_client()
        # Find the cursor doc
        cursor_doc_ref = client.collection(TRANSACTIONS).document(cursor)
        cursor_snap = await cursor_doc_ref.get()
        if cursor_snap.exists:
            query = query.start_after(cursor_snap)
            
    query = query.limit(limit)
    
    transactions = []
    last_doc_id = None
    
    async for doc in query.stream():
        transactions.append(doc.to_dict())
        last_doc_id = doc.id
        
    next_cursor = last_doc_id if len(transactions) == limit else None
    return transactions, next_cursor
