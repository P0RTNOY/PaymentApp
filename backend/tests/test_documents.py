"""Tests for Document Issuance and internal worker."""

import pytest
import base64
import json
from unittest.mock import AsyncMock, patch

from app.modules.documents import ProviderType, DocumentStatus
from app.modules.documents.service import DocumentError


@pytest.fixture
def mock_get_membership():
    """Mock for token validation to always succeed."""
    with patch("app.modules.auth.dependencies.get_membership", new_callable=AsyncMock) as mock_mem:
        mock_mem.return_value = {
            "status": "active",
            "role": "admin",
            "permissions": ["documents.read", "documents.manage"]
        }
        yield mock_mem


@pytest.fixture
def pubsub_payload():
    """Mock pub/sub push payload for transaction completion."""
    data = {"transactionId": "txn_test_for_receipt", "amount": 5000}
    data_b64 = base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")
    
    return {
        "message": {
            "data": data_b64,
            "messageId": "msg_1234",
            "publishTime": "2024-01-01T00:00:00Z",
            "attributes": {
                "eventType": "transaction.completed",
                "tenantId": "t_doc_tenant"
            }
        },
        "subscription": "projects/my-project/subscriptions/txn-processor"
    }


# ── Internal Worker tests (Pub/Sub Push) ─────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.documents.service.get_active_provider_config", new_callable=AsyncMock)
@patch("app.modules.documents.service.get_transaction", new_callable=AsyncMock)
@patch("app.modules.documents.service.get_document_by_transaction", new_callable=AsyncMock)
@patch("app.modules.documents.providers.green_invoice.GreenInvoiceProvider.generate_receipt", new_callable=AsyncMock)
@patch("app.modules.documents.providers.green_invoice.GreenInvoiceProvider.fetch_pdf_content", new_callable=AsyncMock)
@patch("app.modules.documents.service.upload_file", new_callable=AsyncMock)
@patch("app.modules.documents.service.create_document", new_callable=AsyncMock)
@patch("app.modules.documents.service.get_document_by_id", new_callable=AsyncMock)
@patch("app.modules.documents.service.update_document_record", new_callable=AsyncMock)
@patch("app.modules.documents.service.update_transaction", new_callable=AsyncMock)
@patch("app.modules.documents.service.write_audit_event", new_callable=AsyncMock)
async def test_worker_generates_receipt_successfully(
    mock_audit, mock_tx_upd, mock_doc_upd, mock_get_doc_by_id, mock_doc_crt, mock_upload, 
    mock_fetch_pdf, mock_gen_receipt, mock_get_doc, mock_get_txt, mock_get_cfg,
    client, pubsub_payload
):
    """E2E simulation of Pub/Sub push triggering receipt generation (GreenInvoice)."""
    
    # Setup mocks
    mock_get_txt.return_value = {
        "transactionId": "txn_test_for_receipt",
        "tenantId": "t_doc_tenant",
        "status": "completed",
        "amount": 5000,
        "currency": "ILS"
    }
    
    mock_get_doc.return_value = None  # No document yet
    
    mock_get_cfg.return_value = {
        "configId": "pc_123",
        "tenantId": "t_doc_tenant",
        "providerType": "green_invoice",
        "apiKey": "test_key",
        "apiSecret": "test_secret"
    }
    
    mock_gen_receipt.return_value = {
        "provider_document_id": "gi_xyz123",
        "document_number": "1005",
        "pdf_url": "http://mock/pdf",
        "raw_response": {}
    }
    mock_fetch_pdf.return_value = b"%PDF1.4 mock"
    
    # Execute Pub/Sub Push Payload
    response = await client.post(
        "/internal/workers/pubsub/transactions",
        json=pubsub_payload,
        headers={"Authorization": "Bearer mock-pubsub-token"}
    )
    
    assert response.status_code == 200
    assert response.json()["status"] == "ack"
    
    # Verify Orchestration Steps
    mock_get_cfg.assert_called_with("t_doc_tenant")
    mock_gen_receipt.assert_called_once()
    mock_fetch_pdf.assert_called_with("http://mock/pdf")
    mock_upload.assert_called_once()
    # It must have called uploaded with pdf byte array
    assert mock_upload.call_args[0][1] == b"%PDF1.4 mock"
    
    # Firestore mutations
    mock_doc_crt.assert_called_once() # Saves pending state
    mock_doc_upd.assert_called_once() # Updates to issued + doc ID + GCS path
    mock_tx_upd.assert_called_once()  # Links receipt back to transaction


@pytest.mark.asyncio
async def test_worker_rejects_unauthorized_push(client, pubsub_payload):
    """Requires bearer token for internal workers."""
    response = await client.post(
        "/internal/workers/pubsub/transactions",
        json=pubsub_payload
    )
    assert response.status_code == 401


# ── GET Signed URL tests ─────────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.documents.service.get_document_by_id", new_callable=AsyncMock)
@patch("app.modules.documents.service.get_signed_download_url", new_callable=AsyncMock)
async def test_get_document_download_url(
    mock_get_url, mock_get_doc,
    client, mock_get_membership
):
    from app.infra.auth.tokens import create_access_token
    token = create_access_token("u_1", "s_1", "t_doc_tenant")
    
    mock_get_doc.return_value = {
        "documentId": "doc_completed_123",
        "tenantId": "t_doc_tenant",
        "status": DocumentStatus.ISSUED,
        "storagePath": "tenants/t/docs/2024/02/doc.pdf"
    }
    
    mock_get_url.return_value = "https://storage.googleapis.com/mock-signed-url"
    
    response = await client.get(
        "/v1/documents/doc_completed_123/download",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["downloadUrl"] == "https://storage.googleapis.com/mock-signed-url"


@pytest.mark.asyncio
@patch("app.modules.documents.service.get_document_by_id", new_callable=AsyncMock)
async def test_get_document_download_url_pending(
    mock_get_doc,
    client, mock_get_membership
):
    from app.infra.auth.tokens import create_access_token
    token = create_access_token("u_1", "s_1", "t_doc_tenant")
    
    # Document is still pending, so there is no PDF yet
    mock_get_doc.return_value = {
        "documentId": "doc_pending_123",
        "tenantId": "t_doc_tenant",
        "status": DocumentStatus.PENDING,
        "storagePath": None
    }
    
    response = await client.get(
        "/v1/documents/doc_pending_123/download",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "doc.not_ready"
