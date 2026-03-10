"""Domain models for documents and provider configurations."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    PENDING = "pending"
    ISSUED = "issued"
    FAILED = "failed"


class DocumentType(StrEnum):
    RECEIPT = "receipt"
    INVOICE = "invoice"
    INVOICE_RECEIPT = "invoice_receipt"


class ProviderType(StrEnum):
    GREEN_INVOICE = "green_invoice"
    MORNING = "morning"


# ── Provider Configuration ───────────────────────────────────────────────

class ProviderConfigRecord(BaseModel):
    """Firestore provider_configs/{configId} document shape.
    
    Stores tenant-specific credentials for a document provider.
    Credentials should ideally be references to Secret Manager, but for MVP
    may be stored directly if encrypted/secured at rest by Firestore.
    """
    config_id: str = Field(..., alias="configId")
    tenant_id: str = Field(..., alias="tenantId")
    provider_type: ProviderType = Field(..., alias="providerType")
    
    # Provider-specific settings
    api_key: str | None = Field(None, alias="apiKey")
    api_secret: str | None = Field(None, alias="apiSecret")
    webhook_secret: str | None = Field(None, alias="webhookSecret")
    
    is_active: bool = Field(True, alias="isActive")
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


# ── Document (Receipt) ───────────────────────────────────────────────────

class DocumentRecord(BaseModel):
    """Firestore documents/{documentId} document shape."""
    document_id: str = Field(..., alias="documentId")
    tenant_id: str = Field(..., alias="tenantId")
    transaction_id: str = Field(..., alias="transactionId")
    
    type: DocumentType = DocumentType.RECEIPT
    status: DocumentStatus = DocumentStatus.PENDING
    
    provider_type: ProviderType = Field(..., alias="providerType")
    provider_document_id: str | None = Field(None, alias="providerDocumentId")
    document_number: str | None = Field(None, alias="documentNumber")
    
    # GCS Path where the generated PDF is archived
    storage_path: str | None = Field(None, alias="storagePath")
    download_url: str | None = Field(None, alias="downloadUrl")  # Short-lived signed URL or public URL
    
    error_message: str | None = Field(None, alias="errorMessage")
    
    created_at: datetime | None = Field(None, alias="createdAt")
    issued_at: datetime | None = Field(None, alias="issuedAt")

    model_config = {"populate_by_name": True}


# ── API Models ───────────────────────────────────────────────────────────

class ProviderConfigCreate(BaseModel):
    provider_type: ProviderType = Field(..., alias="providerType")
    api_key: str | None = Field(None, alias="apiKey")
    api_secret: str | None = Field(None, alias="apiSecret")

    model_config = {"populate_by_name": True}


class ProviderConfigResponse(BaseModel):
    config_id: str = Field(..., alias="configId")
    provider_type: ProviderType = Field(..., alias="providerType")
    is_active: bool = Field(..., alias="isActive")
    has_api_key: bool = Field(False, alias="hasApiKey")
    has_api_secret: bool = Field(False, alias="hasApiSecret")
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}


class DocumentResponse(BaseModel):
    document_id: str = Field(..., alias="documentId")
    transaction_id: str = Field(..., alias="transactionId")
    type: DocumentType
    status: DocumentStatus
    provider_type: ProviderType = Field(..., alias="providerType")
    document_number: str | None = Field(None, alias="documentNumber")
    download_url: str | None = Field(None, alias="downloadUrl")
    error_message: str | None = Field(None, alias="errorMessage")
    created_at: datetime | None = Field(None, alias="createdAt")
    issued_at: datetime | None = Field(None, alias="issuedAt")

    model_config = {"populate_by_name": True}
