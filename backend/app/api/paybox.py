import logging
import hashlib
import hmac
from typing import Dict, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.modules.transactions.service import ingest_transaction, TransactionError
from app.modules.transactions import TransactionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/providers/paybox", tags=["paybox"])

# Mock secret for Paybox webhook signatures
PAYBOX_WEBHOOK_SECRET = "super_secret_paybox_key"

def verify_paybox_signature(raw_body: bytes, signature: str) -> bool:
    """Verify HMAC signature from PayBox webhook."""
    if not signature:
        return False
    expected_mac = hmac.new(
        PAYBOX_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_mac, signature)


from app.config.rate_limit import limiter

@router.post("/webhook/{tenant_id}")
@limiter.limit("10/minute")
async def paybox_webhook(
    tenant_id: str,
    request: Request,
    x_paybox_signature: str = Header(None)
) -> JSONResponse:
    """
    Ingest a webhook from PayBox.
    1. Verify signature.
    2. Map PayBox payload to standard Canonical Transaction.
    3. Push to `ingest_transaction`.
    """
    raw_body = await request.body()
    
    # We will raise to block unverified requests
    if not verify_paybox_signature(raw_body, x_paybox_signature):
        logger.warning(f"Invalid Paybox signature for tenant {tenant_id}")
        raise HTTPException(status_code=401, detail="Invalid signature")
        
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Example PayBox payload structure mapping
    # { "payboxTxnId": "PB-1234", "amountCents": 10000, "status": "COMPLETED", "customerPhone": "0501234567" }
    
    paybox_txn_id = payload.get("payboxTxnId")
    if not paybox_txn_id:
        return JSONResponse(status_code=200, content={"status": "ignored", "reason": "No payboxTxnId"})

    # Map status
    raw_status = payload.get("status", "PENDING").upper()
    status_map = {
        "COMPLETED": TransactionStatus.COMPLETED,
        "FAILED": TransactionStatus.FAILED,
        "REFUNDED": TransactionStatus.REFUNDED,
        "PENDING": TransactionStatus.PENDING,
    }
    canonical_status = status_map.get(raw_status, TransactionStatus.PENDING)

    amount = payload.get("amountCents", 0)
    customer_phone = payload.get("customerPhone")

    # Build canonical payload
    canonical_payload = {
        "idempotencyKey": f"paybox_{paybox_txn_id}",
        "provider": "paybox",
        "providerTransactionId": paybox_txn_id,
        "amount": amount,
        "currency": "ILS",
        "status": canonical_status,
        "customer": {
            "phone": customer_phone
        } if customer_phone else None,
    }

    try:
        # Ingest into canonical ledger using same logic as Bit
        result = await ingest_transaction(tenant_id, canonical_payload)
        return JSONResponse(status_code=200, content={"status": "success", "transactionId": result.get("transactionId")})
    except TransactionError as e:
        logger.error(f"Failed to ingest Paybox txn: {e.message}")
        if e.status_code == 400:
            # Idempotency hit handled inside ingest_transaction natively usually but just in case
            pass
        return JSONResponse(status_code=e.status_code, content={"error": e.message})
    except Exception as e:
        logger.exception("Unexpected error processing Paybox webhook")
        return JSONResponse(status_code=500, content={"error": "Internal Server Error"})
