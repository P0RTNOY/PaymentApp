"""Domain models for transactions."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field

from app.modules.customers import CustomerResponse


class TransactionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethodDetails(BaseModel):
    """Details of the payment method used."""
    type: str  # e.g., 'credit_card', 'bank_transfer', 'crypto'
    brand: str | None = None  # e.g., 'visa', 'mastercard'
    last4: str | None = None
    expiry_month: int | None = Field(None, alias="expiryMonth")
    expiry_year: int | None = Field(None, alias="expiryYear")

    model_config = {"populate_by_name": True}


class ReceiptStatus(BaseModel):
    """Status of the receipt issuance for this transaction."""
    issued: bool = False
    receipt_id: str | None = Field(None, alias="receiptId")
    document_number: str | None = Field(None, alias="documentNumber")
    issued_at: datetime | None = Field(None, alias="issuedAt")
    error: str | None = None

    model_config = {"populate_by_name": True}


class TransactionRecord(BaseModel):
    """Firestore transactions/{transactionId} document shape."""
    transaction_id: str = Field(..., alias="transactionId")
    tenant_id: str = Field(..., alias="tenantId")
    idempotency_key: str = Field(..., alias="idempotencyKey")
    
    # Provider mapping
    provider: str
    provider_transaction_id: str | None = Field(None, alias="providerTransactionId")
    
    # Amount Details
    amount: int  # smallest currency unit (e.g., cents/agorot)
    currency: str = "ILS"
    
    status: TransactionStatus = TransactionStatus.PENDING
    payment_method: PaymentMethodDetails | None = Field(None, alias="paymentMethod")
    
    # Links
    customer_id: str | None = Field(None, alias="customerId")
    receipt: ReceiptStatus = Field(default_factory=ReceiptStatus)
    
    # Raw data & extensibility
    metadata: dict[str, str] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    completed_at: datetime | None = Field(None, alias="completedAt")

    model_config = {"populate_by_name": True}


# ── API Request/Response Models ──────────────────────────────────────────

class CustomerIngestInput(BaseModel):
    """Customer data payload for inline Upsert during transaction ingestion."""
    customer_id: str | None = Field(None, alias="customerId")
    name: str | None = None
    email: str | None = None
    tax_id: str | None = Field(None, alias="taxId")
    phone: str | None = None

    model_config = {"populate_by_name": True}


class TransactionIngestRequest(BaseModel):
    """POST /v1/transactions request body."""
    idempotency_key: str = Field(..., alias="idempotencyKey")
    provider: str
    provider_transaction_id: str | None = Field(None, alias="providerTransactionId")
    amount: int
    currency: str = "ILS"
    status: TransactionStatus
    payment_method: PaymentMethodDetails | None = Field(None, alias="paymentMethod")
    customer: CustomerIngestInput | None = None
    metadata: dict[str, str] | None = None

    model_config = {"populate_by_name": True}


class TransactionResponse(BaseModel):
    """GET /v1/transactions/{id} response data."""
    transaction_id: str = Field(..., alias="transactionId")
    provider: str
    provider_transaction_id: str | None = Field(None, alias="providerTransactionId")
    amount: int
    currency: str
    status: TransactionStatus
    payment_method: PaymentMethodDetails | None = Field(None, alias="paymentMethod")
    customer: CustomerResponse | None = None
    receipt: ReceiptStatus
    metadata: dict[str, str]
    created_at: datetime | None = Field(None, alias="createdAt")
    completed_at: datetime | None = Field(None, alias="completedAt")

    model_config = {"populate_by_name": True}
