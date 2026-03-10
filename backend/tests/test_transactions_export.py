import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.api.transactions import router
from app.main import app
from app.modules.auth.dependencies import get_current_user

client = TestClient(app)

class MockUser:
    def __init__(self, tenant_id="test-tenant-123", roles=["transactions.read"]):
        self.tenant_id = tenant_id
        self.roles = roles
        
    def has_permission(self, permission: str) -> bool:
        return True

def override_get_current_user():
    return MockUser()

app.dependency_overrides[get_current_user] = override_get_current_user


@patch("app.api.transactions.list_transactions")
def test_export_transactions_csv(mock_list):
    # Mock return 2 pages
    mock_list.side_effect = [
        {
            "items": [
                {"transactionId": "txn_1", "provider": "bit", "amount": 1000},
                {"transactionId": "txn_2", "provider": "paybox", "amount": 2000}
            ],
            "meta": {"cursor": "next_page_token"}
        },
        {
            "items": [
                {"transactionId": "txn_3", "provider": "bit", "amount": 3000}
            ],
            "meta": {"cursor": None}
        }
    ]

    response = client.get("/v1/transactions/export/csv")
    
    # Needs a 401/403 test or success with mock user
    # Our dependency wrapper `require_permission` uses `get_current_user`.
    # Let's just verify the endpoint returns CSV format.
    
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/csv; charset=utf-8"
    assert "attachment; filename=transactions_export.csv" in response.headers["Content-Disposition"]
    
    content = response.text
    # Check headers
    assert "transactionId,provider,providerTransactionId,amount,currency,status,customerId,createdAt" in content
    # Check data
    assert "txn_1,bit,,1000,,,," in content
    assert "txn_2,paybox,,2000,,,," in content
    assert "txn_3,bit,,3000,,,," in content
    
    assert mock_list.call_count == 2
