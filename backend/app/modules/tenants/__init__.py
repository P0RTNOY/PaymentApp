"""Domain models for tenants and memberships."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────

class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"


class MembershipRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# ── Tenant ───────────────────────────────────────────────────────────────

class BrandingSettings(BaseModel):
    """Tenant branding configuration."""
    logo_url: str | None = Field(None, alias="logoUrl")
    primary_color: str | None = Field(None, alias="primaryColor")
    sender_name: str | None = Field(None, alias="senderName")

    model_config = {"populate_by_name": True}


class TenantRecord(BaseModel):
    """Firestore tenants/{tenantId} document shape."""
    tenant_id: str = Field(..., alias="tenantId")
    name: str
    legal_name: str | None = Field(None, alias="legalName")
    country_code: str = Field("IL", alias="countryCode")
    timezone: str = "Asia/Jerusalem"
    currency: str = "ILS"
    status: TenantStatus = TenantStatus.ACTIVE
    branding: BrandingSettings = Field(default_factory=BrandingSettings)
    default_document_provider_id: str | None = Field(None, alias="defaultDocumentProviderId")
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


# ── Tenant Membership ────────────────────────────────────────────────────

class MembershipRecord(BaseModel):
    """Firestore tenant_memberships/{tenantId_userId} document shape."""
    tenant_id: str = Field(..., alias="tenantId")
    user_id: str = Field(..., alias="userId")
    role: MembershipRole = MembershipRole.OPERATOR
    permissions: list[str] = Field(default_factory=list)
    status: str = "active"
    created_at: datetime | None = Field(None, alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}

    @property
    def doc_id(self) -> str:
        """Document ID: {tenantId}_{userId}."""
        return f"{self.tenant_id}_{self.user_id}"


# ── Default permissions by role ──────────────────────────────────────────

DEFAULT_ROLE_PERMISSIONS: dict[MembershipRole, list[str]] = {
    MembershipRole.OWNER: [
        "tenants.manage",
        "providers.manage",
        "transactions.read",
        "transactions.manage",
        "documents.read",
        "documents.issue",
        "customers.read",
        "customers.manage",
        "audit.read",
        "sync.manage",
        "users.manage",
    ],
    MembershipRole.ADMIN: [
        "providers.manage",
        "transactions.read",
        "transactions.manage",
        "documents.read",
        "documents.issue",
        "customers.read",
        "customers.manage",
        "audit.read",
        "sync.manage",
    ],
    MembershipRole.OPERATOR: [
        "transactions.read",
        "transactions.manage",
        "documents.read",
        "documents.issue",
        "customers.read",
    ],
    MembershipRole.VIEWER: [
        "transactions.read",
        "documents.read",
        "customers.read",
    ],
}
