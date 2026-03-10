"""Green Invoice document provider implementation."""

from __future__ import annotations

import logging
from typing import Any

from app.modules.documents.providers.base import DocumentProvider, ProviderError

logger = logging.getLogger(__name__)


class GreenInvoiceProvider(DocumentProvider):
    """
    Integration with Green Invoice (Morning) API.
    
    Note: For the MVP and testing purposes, this is a mock implementation
    that simulates an API call and returns a deterministic response.
    In a real-world scenario, this would use httpx to call https://api.greeninvoice.co.il/api/v1
    """

    def __init__(self, api_key: str, api_secret: str, tenant_id: str):
        super().__init__(api_key, api_secret, tenant_id)
        self.base_url = "https://api.greeninvoice.co.il/api/v1"
        self._jwt_token: str | None = None

    async def _authenticate(self) -> str:
        """Simulate authenticating with ID/Secret to get a JWT."""
        # Genuine flow: POST /account/token
        logger.info("Mock authenticating with GreenInvoice")
        self._jwt_token = "mock_greeninvoice_jwt"
        return self._jwt_token

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
        Simulate generating a document in GreenInvoice.
        Document Type 320 = Receipt.
        """
        if not self._jwt_token:
            await self._authenticate()

        # Genuine flow: POST /documents
        # Payload would include type=320, client details, income row, payment details.
        
        logger.info(
            "Mock generating receipt with GreenInvoice",
            extra={"transactionId": transaction_id, "amount": amount}
        )
        
        # Simulate a network call delay or failure if needed here.
        # For now, return a successful mock response.
        
        mock_uuid = f"gi_{transaction_id[-8:]}"
        mock_doc_number = "10492"
        mock_pdf_url = f"https://api.greeninvoice.co.il/api/v1/documents/{mock_uuid}/pdf"

        return {
            "provider_document_id": mock_uuid,
            "document_number": mock_doc_number,
            "pdf_url": mock_pdf_url,
            "raw_response": {"id": mock_uuid, "type": 320, "documentNumber": mock_doc_number}
        }

    async def fetch_pdf_content(self, pdf_url: str) -> bytes:
        """
        Simulates fetching the raw PDF bytes from the provider.
        """
        # Genuine flow: GET pdf_url with JWT header
        logger.info(f"Mock fetching PDF bytes from {pdf_url}")
        
        # Mock a minimal valid PDF-like byte array
        return b"%PDF-1.4\n%MockReceipt\n%%EOF"
