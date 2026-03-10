import pytest
import hmac
import hashlib
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.api.paybox import PAYBOX_WEBHOOK_SECRET
from app.main import app

client = TestClient(app)

@patch("app.api.paybox.ingest_transaction")
def test_paybox_webhook_success(mock_ingest):
    mock_ingest.return_value = {"transactionId": "txn_fake_123"}
    
    tenant_id = "test-tenant-123"
    payload = b'{"payboxTxnId":"PB-999","amountCents":5500,"status":"COMPLETED","customerPhone":"0501234567"}'
    
    signature = hmac.new(
        PAYBOX_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    response = client.post(
        f"/v1/providers/paybox/webhook/{tenant_id}",
        content=payload,
        headers={"x-paybox-signature": signature}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    
    # Verify the mapping was correct
    mock_ingest.assert_called_once()
    called_tenant, called_payload = mock_ingest.call_args[0]
    assert called_tenant == tenant_id
    assert called_payload["provider"] == "paybox"
    assert called_payload["providerTransactionId"] == "PB-999"
    assert called_payload["amount"] == 5500
    assert called_payload["status"] == "completed"

def test_paybox_webhook_invalid_signature():
    tenant_id = "test-tenant-123"
    payload = b'{"payboxTxnId":"PB-999"}'
    
    response = client.post(
        f"/v1/providers/paybox/webhook/{tenant_id}",
        content=payload,
        headers={"x-paybox-signature": "bad_signature"}
    )
    
    # Since we enforce signature verification, this should now return 401
    assert response.status_code == 401

def test_paybox_webhook_invalid_json():
    tenant_id = "test-tenant-123"
    payload = b'invalid json'
    
    signature = hmac.new(
        PAYBOX_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    response = client.post(
        f"/v1/providers/paybox/webhook/{tenant_id}",
        content=payload,
        headers={"x-paybox-signature": signature}
    )
    assert response.status_code == 400
