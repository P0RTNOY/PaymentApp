"""Tests for transaction ingestion API and logic."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.modules.auth.dependencies import CurrentUser


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_auth_headers(token: str = "mocked-token") -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_current_user():
    """Mock get_current_user dependency so endpoints are protected but accessible in tests."""
    user = CurrentUser(
        user_id="u_admin_123",
        session_id="s_123",
        tenant_id="t_test123",
        role="admin",
        permissions=["transactions.read", "transactions.manage"]
    )
    with patch("app.modules.auth.dependencies.get_current_user", return_value=user):
        yield user


@pytest.fixture
def mock_get_membership():
    """Mock for token validation to always succeed."""
    with patch("app.modules.auth.dependencies.get_membership", new_callable=AsyncMock) as mock_mem:
        mock_mem.return_value = {
            "status": "active",
            "role": "admin",
            "permissions": ["transactions.read", "transactions.manage"]
        }
        yield mock_mem


@pytest.fixture
def valid_ingest_payload():
    return {
        "idempotencyKey": "idem_12345",
        "provider": "payplus",
        "providerTransactionId": "pp_9876",
        "amount": 10050,  # 100.50 ILS
        "currency": "ILS",
        "status": "completed",
        "paymentMethod": {
            "type": "credit_card",
            "brand": "visa",
            "last4": "4242",
            "expiryMonth": 12,
            "expiryYear": 2028
        },
        "customer": {
            "name": "John Doe",
            "email": "john@doe.com",
            "taxId": "123456789"
        },
        "metadata": {"source": "mobile"}
    }


def _make_transaction_doc(
    txn_id="txn_test123",
    tenant_id="t_test123",
    idem_key="idem_12345",
    status="completed",
    customer_id="cus_abc",
    amount=10050
):
    return {
        "transactionId": txn_id,
        "tenantId": tenant_id,
        "idempotencyKey": idem_key,
        "provider": "payplus",
        "amount": amount,
        "currency": "ILS",
        "status": status,
        "paymentMethod": {"type": "credit_card"},
        "customerId": customer_id,
        "metadata": {},
        "receipt": {"issued": False, "receiptId": None},
        "createdAt": datetime.now(timezone.utc),
        "completedAt": datetime.now(timezone.utc) if status == "completed" else None
    }


def _make_customer_doc(
    customer_id="cus_abc",
    tenant_id="t_test123",
    tax_id="123456789",
    email="john@doe.com"
):
    return {
        "customerId": customer_id,
        "tenantId": tenant_id,
        "name": "John Doe",
        "taxId": tax_id,
        "email": email,
        "phone": None,
        "address": None,
        "metadata": {},
        "createdAt": datetime.now(timezone.utc)
    }


# ── Ingestion Logic Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.transactions.service.publish_event", new_callable=AsyncMock)
@patch("app.modules.transactions.service.write_audit_event", new_callable=AsyncMock)
@patch("app.modules.transactions.service.create_transaction", new_callable=AsyncMock)
@patch("app.modules.transactions.service.get_transaction", new_callable=AsyncMock)
@patch("app.modules.transactions.service.get_customer", new_callable=AsyncMock)
@patch("app.modules.transactions.service.find_customer_by_tax_id", new_callable=AsyncMock)
@patch("app.modules.transactions.service.find_transaction_by_idempotency_key", new_callable=AsyncMock)
async def test_ingest_transaction_success_with_customer_upsert(
    mock_find_tx, mock_find_tax_id, mock_get_customer, mock_get_transaction,
    mock_create_tx, mock_audit, mock_publish,
    client, valid_ingest_payload, mock_get_membership
):
    """POST /v1/transactions with new idempotency key, hits upside flow."""
    from app.infra.auth.tokens import create_access_token
    access_token = create_access_token("u_admin_123", "s_123", "t_test123")

    mock_find_tx.return_value = None  # No duplicate
    
    # 1. Tax ID lookup matches an existing customer
    mock_find_tax_id.return_value = _make_customer_doc()
    
    # After creation, the service fetches transaction to return
    txn_doc = _make_transaction_doc()
    mock_get_transaction.return_value = txn_doc
    mock_get_customer.return_value = _make_customer_doc()

    response = await client.post(
        "/v1/transactions", 
        json=valid_ingest_payload,
        headers=_make_auth_headers(access_token)
    )

    assert response.status_code == 201
    
    # Was pubsub triggered? (since status is 'completed')
    mock_publish.assert_called_once()
    args, kwargs = mock_publish.call_args
    assert kwargs["event_type"] == "transaction.completed"
    
    # Assert data was returned mapped correctly
    data = response.json()["data"]
    assert data["transactionId"] == txn_doc["transactionId"]
    assert data["customer"]["taxId"] == "123456789"


@pytest.mark.asyncio
@patch("app.modules.transactions.service.find_transaction_by_idempotency_key", new_callable=AsyncMock)
@patch("app.modules.transactions.service.get_customer", new_callable=AsyncMock)
async def test_ingest_idempotency_hit(
    mock_get_customer, mock_find_tx, 
    client, valid_ingest_payload, mock_get_membership
):
    """POST /v1/transactions with existing idempotency key yields 201 returning existing."""
    from app.infra.auth.tokens import create_access_token
    access_token = create_access_token("u_admin_123", "s_123", "t_test123")

    # Idempotency hit!
    mock_find_tx.return_value = _make_transaction_doc()
    
    response = await client.post(
        "/v1/transactions", 
        json=valid_ingest_payload,
        headers=_make_auth_headers(access_token)
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["transactionId"] == "txn_test123"


# ── Listing and Retrieval Tests ──────────────────────────────────────────

@pytest.mark.asyncio
@patch("app.modules.transactions.service.list_tenant_transactions", new_callable=AsyncMock)
async def test_list_transactions(
    mock_list, client, mock_get_membership
):
    """GET /v1/transactions with valid role."""
    from app.infra.auth.tokens import create_access_token
    access_token = create_access_token("u_admin_123", "s_123", "t_test123")
    
    mock_list.return_value = ([_make_transaction_doc()], "next_cursor_xyz")
    
    response = await client.get(
        "/v1/transactions",
        headers=_make_auth_headers(access_token)
    )
    
    assert response.status_code == 200
    res = response.json()
    assert len(res["data"]) == 1
    assert res["meta"]["pagination"]["hasMore"] is True
    assert res["meta"]["pagination"]["cursor"] == "next_cursor_xyz"


@pytest.mark.asyncio
async def test_list_transactions_missing_permissions(
    client
):
    """GET /v1/transactions without correct permission gets 403."""
    from app.infra.auth.tokens import create_access_token
    access_token = create_access_token("u_admin_123", "s_123", "t_test123")
    
    # Not using the mock_get_membership fixture, we'll patch our own
    with patch("app.modules.auth.dependencies.get_membership", new_callable=AsyncMock) as mock_mem:
        mock_mem.return_value = {
            "status": "active",
            "role": "viewer",
            "permissions": ["documents.read"]  # Missing transactions.read
        }
    
        response = await client.get(
            "/v1/transactions",
            headers=_make_auth_headers(access_token)
        )
        
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "auth.insufficient_permission"


@pytest.mark.asyncio
@patch("app.modules.transactions.service.get_transaction", new_callable=AsyncMock)
@patch("app.modules.transactions.service.get_customer", new_callable=AsyncMock)
async def test_get_single_transaction(
    mock_get_customer, mock_get_transaction, 
    client, mock_get_membership
):
    """GET /v1/transactions/{id}."""
    from app.infra.auth.tokens import create_access_token
    access_token = create_access_token("u_admin_123", "s_123", "t_test123")
    
    mock_get_transaction.return_value = _make_transaction_doc(txn_id="txn_test123")
    mock_get_customer.return_value = _make_customer_doc()
    
    response = await client.get(
        "/v1/transactions/txn_test123",
        headers=_make_auth_headers(access_token)
    )
    
    assert response.status_code == 200
    res = response.json()
    assert res["data"]["transactionId"] == "txn_test123"
    assert res["data"]["customer"]["taxId"] == "123456789"
