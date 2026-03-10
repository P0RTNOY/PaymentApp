"""Document API router and Pub/Sub Worker subscriber endpoint."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.config.logging import request_id_var
from app.modules.auth.dependencies import CurrentUser, get_current_user, require_permission
from app.modules.documents.service import (
    DocumentError,
    generate_receipt_for_transaction,
    get_document_download_url,
)
from app.infra.pubsub import verify_pubsub_jwt

logger = logging.getLogger(__name__)

# Main API Router
router = APIRouter(prefix="/v1/documents", tags=["documents"])

# Internal Background Worker Router
worker_router = APIRouter(prefix="/internal/workers", tags=["workers"])


def _req_id() -> str:
    return request_id_var.get() or "unknown"


def _wrap(data: dict | str, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"data": data, "meta": {"requestId": _req_id()}},
    )


def _err(e: DocumentError) -> JSONResponse:
    return JSONResponse(
        status_code=e.status_code,
        content={
            "error": {"code": e.code, "message": e.message},
            "meta": {"requestId": _req_id()},
        },
    )


# ── Public API ──────────────────────────────────────────────────────────

@router.get("/{document_id}/download")
async def get_document_url(
    document_id: str,
    current_user: Annotated[CurrentUser, Depends(require_permission("documents.read"))]
) -> JSONResponse:
    """
    Get a short-lived signed URL to securely download the document PDF.
    """
    try:
        url = await get_document_download_url(current_user.tenant_id, document_id)
        # We can return the URL in the data payload, or issue a 302 Redirect.
        # Returning as JSON API response as per typical SPA behavior.
        return _wrap({"downloadUrl": url}, 200)
    except DocumentError as e:
        return _err(e)


# ── Internal Pub/Sub Push Endpoint ───────────────────────────────────────

@worker_router.post("/pubsub/transactions")
async def process_transaction_event(request: Request) -> JSONResponse:
    """
    Internal endpoint triggered by Cloud Pub/Sub via push subscription.
    Listens for 'transaction.completed' events to generate receipts asynchronously.
    """
    # 1. Verify caller is Pub/Sub (OIDC token validation)
    # This ensures only GCP Pub/Sub can hit this endpoint.
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        logger.warning("PubSub endpoint called without Bearer token")
        return JSONResponse(status_code=401, content={})
        
    token = auth_header.split(" ")[1]
    is_valid = await verify_pubsub_jwt(token)
    if not is_valid:
        logger.warning("Invalid PubSub JWT token")
        return JSONResponse(status_code=403, content={})

    # 2. Parse Pub/Sub envelope
    try:
        envelope = await request.json()
        message = envelope.get("message", {})
        attributes = message.get("attributes", {})
        
        event_type = attributes.get("eventType")
        tenant_id = attributes.get("tenantId")
        
        # Base64 decode the data payload
        import base64
        import json
        if "data" in message:
            data_bytes = base64.b64decode(message["data"])
            payload = json.loads(data_bytes)
        else:
            payload = {}
            
    except Exception as e:
        logger.error(f"Failed to parse Pub/Sub envelope: {e}")
        return JSONResponse(status_code=400, content={})

    # 3. Handle specific events
    logger.info(f"Processing PubSub event: {event_type} for tenant {tenant_id}")
    
    if event_type == "transaction.completed":
        transaction_id = payload.get("transactionId")
        if not transaction_id or not tenant_id:
            logger.error("Missing transactionId or tenantId in event payload")
            return JSONResponse(status_code=200, content={}) # Ack to discard
            
        try:
            # Execute the heavy lifting: generate receipt and upload to GCS
            await generate_receipt_for_transaction(tenant_id, transaction_id)
        except DocumentError as e:
            logger.error(f"Document generation failed (business logic): {e.message}")
            # Acknowledging (200) for business logic failures so it doesn't infinitely retry.
            # It's recorded in Firestore as FAILED status for manual intervention.
            pass
        except Exception as e:
            logger.exception("Unexpected error during document generation")
            # Returning 500 nacks the message so Pub/Sub retries it later.
            return JSONResponse(status_code=500, content={})

    # Return 200 OK to acknowledge the message successfully
    return JSONResponse(status_code=200, content={"status": "ack"})
