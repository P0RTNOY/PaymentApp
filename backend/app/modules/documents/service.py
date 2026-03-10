"""Document service — orchestration of receipt generation and storage."""

from __future__ import annotations

import logging
from typing import Any

from app.modules.documents import DocumentStatus, DocumentType
from app.modules.documents.repository import (
    get_active_provider_config,
    create_document,
    get_document_by_transaction,
    update_document_record,
    generate_document_id,
    get_document_by_id,
)
from app.modules.transactions.repository import (
    get_transaction,
    update_transaction,
)
from app.modules.documents.providers.base import get_provider, ProviderError
from app.modules.audit.repository import write_audit_event
from app.infra.gcs import upload_file, get_signed_download_url

logger = logging.getLogger(__name__)


class DocumentError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def generate_receipt_for_transaction(tenant_id: str, transaction_id: str) -> dict[str, Any]:
    """
    Orchestrates finding the provider, creating a document record, calling the provider,
    fetching the PDF, uploading to GCS, and updating the transaction.
    """
    txn = await get_transaction(transaction_id)
    if not txn or txn.get("tenantId") != tenant_id:
        raise DocumentError("doc.txn_not_found", "Transaction not found", 404)
        
    if txn.get("status") != "completed":
        raise DocumentError("doc.txn_not_completed", "Cannot issue receipt for incomplete transaction", 400)
        
    # Idempotency check: does a document already exist for this transaction?
    existing_doc = await get_document_by_transaction(tenant_id, transaction_id)
    if existing_doc and existing_doc.get("status") == DocumentStatus.ISSUED:
        logger.info("Receipt already issued for transaction", extra={"transactionId": transaction_id})
        return existing_doc
        
    # Get active provider config
    provider_config = await get_active_provider_config(tenant_id)
    if not provider_config:
        error_msg = "No active document provider configuration found for tenant"
        logger.error(error_msg, extra={"tenantId": tenant_id})
        await _fail_receipt(tenant_id, transaction_id, existing_doc, error_msg)
        raise DocumentError("doc.no_provider", error_msg, 400)
        
    provider_type = provider_config["providerType"]
    api_key = provider_config.get("apiKey")
    api_secret = provider_config.get("apiSecret")
    
    if not api_key or not api_secret:
        error_msg = f"Provider config {provider_config['configId']} missing credentials"
        await _fail_receipt(tenant_id, transaction_id, existing_doc, error_msg)
        raise DocumentError("doc.invalid_provider_config", error_msg, 500)
        
    # Instantiate provider
    try:
        provider = get_provider(provider_type, api_key, api_secret, tenant_id)
    except ValueError as e:
        await _fail_receipt(tenant_id, transaction_id, existing_doc, str(e))
        raise DocumentError("doc.unsupported_provider", str(e), 500)
        
    # Create pending document record if not exists
    doc_id = existing_doc["documentId"] if existing_doc else generate_document_id()
    if not existing_doc:
        await create_document({
            "documentId": doc_id,
            "tenantId": tenant_id,
            "transactionId": transaction_id,
            "type": DocumentType.RECEIPT,
            "status": DocumentStatus.PENDING,
            "providerType": provider_type,
            "providerDocumentId": None,
            "documentNumber": None,
            "storagePath": None,
            "downloadUrl": None,
            "errorMessage": None
        })
        
    # Prepare payload for provider
    # Basic data extraction from transaction (in a real app, hydrate full customer details here)
    amount = txn.get("amount", 0)
    currency = txn.get("currency", "ILS")
    
    # Try to issue the receipt via provider
    try:
        receipt_result = await provider.generate_receipt(
            transaction_id=transaction_id,
            amount=amount,
            currency=currency,
            customer_name="Customer",  # Would use hydrated customer in prod
            customer_email=None,
            description=f"Payment {transaction_id}"
        )
        
        provider_doc_id = receipt_result["provider_document_id"]
        doc_number = receipt_result["document_number"]
        pdf_url = receipt_result["pdf_url"]
        
        # Fetch the PDF bytes from the provider
        pdf_bytes = await provider.fetch_pdf_content(pdf_url)
        
        # Upload to GCS
        # Spec format: gs://{bucket}/tenants/{tenantId}/documents/{year}/{month}/{documentId}.pdf
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        gcs_path = f"tenants/{tenant_id}/documents/{now.year}/{now.month:02d}/{doc_id}.pdf"
        
        await upload_file(gcs_path, pdf_bytes, "application/pdf")
        
        # Update document record
        await update_document_record(doc_id, {
            "status": DocumentStatus.ISSUED,
            "providerDocumentId": provider_doc_id,
            "documentNumber": doc_number,
            "storagePath": gcs_path,
            "errorMessage": None
        })
        
        # Update transaction with receipt summary
        await update_transaction(transaction_id, {
            "receipt": {
                "issued": True,
                "receiptId": doc_id,
                "documentNumber": doc_number,
                "error": None
            }
        })
        
        # Audit
        await write_audit_event({
            "tenantId": tenant_id,
            "entityType": "document",
            "entityId": doc_id,
            "eventType": "document.issued",
            "actorType": "system",
            "actorId": "document_service",
            "payload": {"transactionId": transaction_id, "documentNumber": doc_number}
        })
        
        # Return complete document object
        return await get_document_by_id(doc_id)  # type: ignore

    except Exception as e:
        logger.exception("Failed to issue receipt via provider")
        await _fail_receipt(tenant_id, transaction_id, existing_doc or {"documentId": doc_id}, str(e))
        raise DocumentError("doc.provider_failed", f"Failed to issue receipt: {str(e)}", 500)


async def _fail_receipt(tenant_id: str, transaction_id: str, existing_doc: dict | None, error_msg: str) -> None:
    """Helper to mark document and transaction receipt status as failed."""
    if existing_doc:
        await update_document_record(existing_doc["documentId"], {
            "status": DocumentStatus.FAILED,
            "errorMessage": error_msg
        })
        
    await update_transaction(transaction_id, {
        "receipt": {
            "issued": False,
            "receiptId": existing_doc["documentId"] if existing_doc else None,
            "error": error_msg
        }
    })
    
    await write_audit_event({
        "tenantId": tenant_id,
        "entityType": "transaction",
        "entityId": transaction_id,
        "eventType": "document.failed",
        "actorType": "system",
        "actorId": "document_service",
        "payload": {"error": error_msg}
    })


async def get_document_download_url(tenant_id: str, document_id: str) -> str:
    """Gets a short-lived signed URL for downloading the document PDF."""
    doc = await get_document_by_id(document_id)
    if not doc or doc.get("tenantId") != tenant_id:
        raise DocumentError("doc.not_found", "Document not found", 404)
        
    storage_path = doc.get("storagePath")
    if not storage_path or doc.get("status") != DocumentStatus.ISSUED:
        raise DocumentError("doc.not_ready", "Document PDF is not available", 404)
        
    return await get_signed_download_url(storage_path, expiration_minutes=15)
