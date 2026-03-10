"""Domain models for customers."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, EmailStr


class CustomerRecord(BaseModel):
    """Firestore customers/{customerId} document shape."""
    customer_id: str = Field(..., alias="customerId")
    tenant_id: str = Field(..., alias="tenantId")
    name: str | None = None
    tax_id: str | None = Field(None, alias="taxId")
    email: str | None = None
    phone: str | None = None
    address: dict[str, str] | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class CustomerResponse(BaseModel):
    """Public customer profile returned in API responses."""
    customer_id: str = Field(..., alias="customerId")
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    tax_id: str | None = Field(None, alias="taxId")
    created_at: datetime | None = Field(None, alias="createdAt")

    model_config = {"populate_by_name": True}
