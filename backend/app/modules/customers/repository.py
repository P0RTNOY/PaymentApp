"""Firestore repository for customers."""

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

CUSTOMERS = "customers"


def generate_customer_id() -> str:
    return f"cus_{ulid.new().str.lower()}"


async def create_customer(customer_data: dict[str, Any]) -> None:
    """Create a new customer document."""
    customer_data["createdAt"] = server_timestamp()
    customer_data["updatedAt"] = server_timestamp()
    await set_document(CUSTOMERS, customer_data["customerId"], customer_data)
    logger.info("Created customer", extra={"customerId": customer_data["customerId"]})


async def get_customer(customer_id: str) -> dict[str, Any] | None:
    """Fetch customer document by ID."""
    return await get_document(CUSTOMERS, customer_id)


async def update_customer(customer_id: str, updates: dict[str, Any]) -> None:
    """Partially update customer fields."""
    updates["updatedAt"] = server_timestamp()
    await update_document(CUSTOMERS, customer_id, updates)


async def find_customer_by_email(tenant_id: str, email: str) -> dict[str, Any] | None:
    """Find a customer by tenant and email."""
    coll = collection(CUSTOMERS)
    query = coll.where("tenantId", "==", tenant_id).where("email", "==", email.lower()).limit(1)
    
    async for doc in query.stream():
        return doc.to_dict()
    return None


async def find_customer_by_tax_id(tenant_id: str, tax_id: str) -> dict[str, Any] | None:
    """Find a customer by tenant and tax ID."""
    coll = collection(CUSTOMERS)
    query = coll.where("tenantId", "==", tenant_id).where("taxId", "==", tax_id).limit(1)
    
    async for doc in query.stream():
        return doc.to_dict()
    return None
