"""Transaction service — orchestration logic for payment ingestion."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import get_settings
from app.modules.customers.repository import (
    create_customer,
    update_customer,
    get_customer,
    find_customer_by_email,
    find_customer_by_tax_id,
    generate_customer_id,
)
from app.modules.transactions.repository import (
    create_transaction,
    get_transaction,
    update_transaction,
    find_transaction_by_idempotency_key,
    list_tenant_transactions,
    generate_transaction_id,
)
from app.modules.audit.repository import write_audit_event
from app.infra.pubsub import publish_event


logger = logging.getLogger(__name__)


class TransactionError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def _upsert_customer(tenant_id: str, customer_data: dict) -> str | None:
    """Find existing or create new customer based on ID, Tax ID, or Email."""
    if not customer_data:
        return None

    customer_id = customer_data.get("customerId")
    
    # 1. By direct ID
    if customer_id:
        existing = await get_customer(customer_id)
        if existing and existing.get("tenantId") == tenant_id:
            # We could optionally update the existing customer here if data changed
            return customer_id
            
    # 2. By Tax ID
    tax_id = customer_data.get("taxId")
    if tax_id:
        existing = await find_customer_by_tax_id(tenant_id, tax_id)
        if existing:
            return existing["customerId"]
            
    # 3. By Email
    email = customer_data.get("email")
    if email:
        existing = await find_customer_by_email(tenant_id, email)
        if existing:
            return existing["customerId"]
            
    # 4. Create new
    customer_id = generate_customer_id()
    new_cust = {
        "customerId": customer_id,
        "tenantId": tenant_id,
        "name": customer_data.get("name"),
        "taxId": tax_id,
        "email": email.lower() if email else None,
        "phone": customer_data.get("phone"),
        "address": None,
        "metadata": {},
    }
    await create_customer(new_cust)
    return customer_id


async def ingest_transaction(tenant_id: str, payload: dict) -> dict:
    """
    Ingest a new transaction.
    1. Check Idempotency.
    2. Upsert Customer.
    3. Save Transaction.
    4. Emit Pub/Sub event for upstream components (receipt issuance).
    """
    idempotency_key = payload.get("idempotencyKey")
    if not idempotency_key:
        raise TransactionError("txn.missing_idempotency_key", "idempotencyKey is required")
        
    # Idempotency check
    existing_txn = await find_transaction_by_idempotency_key(tenant_id, idempotency_key)
    if existing_txn:
        logger.info(
            "Idempotency hit", 
            extra={"tenantId": tenant_id, "idempotencyKey": idempotency_key, "transactionId": existing_txn["transactionId"]}
        )
        return existing_txn
        
    # Resolve customer
    customer_id = await _upsert_customer(tenant_id, payload.get("customer") or {})
    
    # Create transaction
    transaction_id = generate_transaction_id()
    
    # Map raw input to document
    txn_data = {
        "transactionId": transaction_id,
        "tenantId": tenant_id,
        "idempotencyKey": idempotency_key,
        "provider": payload.get("provider"),
        "providerTransactionId": payload.get("providerTransactionId"),
        "amount": payload.get("amount"),
        "currency": payload.get("currency", "ILS"),
        "status": payload.get("status", "pending"),
        "paymentMethod": payload.get("paymentMethod"),
        "customerId": customer_id,
        "metadata": payload.get("metadata", {}),
        "receipt": {
            "issued": False,
            "receiptId": None,
            "documentNumber": None,
            "issuedAt": None,
            "error": None
        }
    }
    
    # Set completion timestamp if already completed
    if txn_data["status"] == "completed":
        txn_data["completedAt"] = datetime.now(timezone.utc)
    else:
        txn_data["completedAt"] = None
        
    await create_transaction(txn_data)
    
    # Audit log
    await write_audit_event({
        "tenantId": tenant_id,
        "entityType": "transaction",
        "entityId": transaction_id,
        "eventType": "transaction.ingested",
        "actorType": "system",
        "actorId": "ingestion_api",
        "payload": {
            "provider": txn_data["provider"],
            "status": txn_data["status"],
            "amount": txn_data["amount"]
        }
    })
    
    # Trigger downstream processors via Pub/Sub IF completed
    if txn_data["status"] == "completed":
        await publish_event(
            topic_id=get_settings().pubsub_transaction_topic,
            event_type="transaction.completed",
            tenant_id=tenant_id,
            data={
                "transactionId": transaction_id,
                "customerId": customer_id,
                "provider": txn_data["provider"],
                "amount": txn_data["amount"]
            },
            ordering_key=tenant_id
        )

    # Return full state including mapped customer
    return await get_transaction_details(tenant_id, transaction_id)


async def get_transaction_details(tenant_id: str, transaction_id: str) -> dict:
    """Fetch transaction with its nested customer details."""
    txn = await get_transaction(transaction_id)
    if not txn or txn.get("tenantId") != tenant_id:
        raise TransactionError("txn.not_found", "Transaction not found", 404)
        
    # Hydrate customer data
    cust_id = txn.get("customerId")
    if cust_id:
        cust = await get_customer(cust_id)
        if cust:
            txn["customer"] = {
                "customerId": cust["customerId"],
                "name": cust.get("name"),
                "email": cust.get("email"),
                "phone": cust.get("phone"),
                "taxId": cust.get("taxId"),
            }
    
    return txn


async def list_transactions(
    tenant_id: str, 
    limit: int = 50, 
    cursor: str | None = None
) -> dict:
    """List transactions with pagination for the tenant."""
    items, next_cursor = await list_tenant_transactions(tenant_id, limit, cursor)
    
    return {
        "items": items,
        "meta": {
            "cursor": next_cursor,
            "hasMore": next_cursor is not None,
            "limit": limit
        }
    }
