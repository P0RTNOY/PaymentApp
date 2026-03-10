"""Base interface and factory for document providers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from app.modules.documents import ProviderType

logger = logging.getLogger(__name__)


class ProviderError(Exception):
    """Exception raised for provider-specific errors."""
    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class DocumentProvider(ABC):
    """Abstract base class for all document issuance providers (e.g., Green Invoice, Morning)."""

    def __init__(self, api_key: str, api_secret: str, tenant_id: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.tenant_id = tenant_id

    @abstractmethod
    async def generate_receipt(
        self,
        transaction_id: str,
        amount: int,
        currency: str,
        customer_name: str | None,
        customer_email: str | None,
        description: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Generate a digital receipt/invoice.
        
        Returns a dictionary containing:
            - provider_document_id: The ID of the document in the external system
            - document_number: Human-readable document number
            - pdf_url: Temporary URL to download the PDF
            - raw_response: Full API response for debugging
        """
        pass


def get_provider(provider_type: str, api_key: str, api_secret: str, tenant_id: str) -> DocumentProvider:
    """Factory method to instantiate the correct provider."""
    # We will import this dynamically or specifically to avoid circular deps if needed
    from app.modules.documents.providers.green_invoice import GreenInvoiceProvider
    
    if provider_type == ProviderType.GREEN_INVOICE:
        return GreenInvoiceProvider(api_key, api_secret, tenant_id)
    
    # Placeholder for future providers
    # if provider_type == ProviderType.MORNING:
    #     return MorningProvider(api_key, api_secret, tenant_id)
        
    raise ValueError(f"Unsupported provider type: {provider_type}")
