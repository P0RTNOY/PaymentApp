"""Transaction API router."""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.config.logging import request_id_var
from app.modules.auth.dependencies import CurrentUser, get_current_user, require_permission
from app.modules.transactions import TransactionIngestRequest
from app.modules.transactions.service import (
    TransactionError,
    ingest_transaction,
    get_transaction_details,
    list_transactions,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/transactions", tags=["transactions"])


def _req_id() -> str:
    return request_id_var.get() or "unknown"


def _wrap(data: dict, status_code: int = 200) -> JSONResponse:
    """Wrap response in standard API envelope."""
    return JSONResponse(
        status_code=status_code,
        content={"data": jsonable_encoder(data), "meta": {"requestId": _req_id()}},
    )


def _err(e: TransactionError) -> JSONResponse:
    """Wrap error into standard error envelope."""
    return JSONResponse(
        status_code=e.status_code,
        content={
            "error": {"code": e.code, "message": e.message},
            "meta": {"requestId": _req_id()},
        },
    )


@router.post("")
async def create_transaction(
    body: TransactionIngestRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission("transactions.manage"))]
) -> JSONResponse:
    """
    Ingest a new transaction. Upserts customer if provided, guards with idempotency key,
    and publishes pubsub event if ready for receipt generation.
    """
    try:
        payload = body.model_dump(by_alias=True)
        result = await ingest_transaction(current_user.tenant_id, payload)
        # 201 Created or 200 OK (if idempotency key reused)
        return _wrap(result, 201)
    except TransactionError as e:
        return _err(e)


@router.get("")
async def get_transactions(
    current_user: Annotated[CurrentUser, Depends(require_permission("transactions.read"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[Optional[str], Query()] = None,
) -> JSONResponse:
    """
    List transactions with cursor-based pagination.
    """
    try:
        result = await list_transactions(current_user.tenant_id, limit, cursor)
        
        # Format response matching API envelope standard
        return JSONResponse(
            status_code=200,
            content={
                "data": jsonable_encoder(result["items"]),
                "meta": {
                    "requestId": _req_id(),
                    "pagination": result["meta"]
                }
            }
        )
    except Exception as e:
        logger.exception("Error listing transactions")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal.unexpected", "message": "Unexpected error"}}
        )


@router.get("/{transaction_id}")
async def get_single_transaction(
    transaction_id: str,
    current_user: Annotated[CurrentUser, Depends(require_permission("transactions.read"))]
) -> JSONResponse:
    """
    Retrieve details of a single transaction including hydrated customer info.
    """
    try:
        result = await get_transaction_details(current_user.tenant_id, transaction_id)
        return _wrap(result, 200)
    except TransactionError as e:
        return _err(e)


import io
import csv
from fastapi.responses import StreamingResponse

@router.get("/export/csv")
async def export_transactions_csv(
    current_user: Annotated[CurrentUser, Depends(require_permission("transactions.read"))]
) -> StreamingResponse:
    """
    Export all transactions for a tenant as a streaming CSV.
    """
    async def iter_csv():
        # Yield byte-encoded header
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "transactionId", "provider", "providerTransactionId", "amount",
            "currency", "status", "customerId", "createdAt"
        ])
        yield output.getvalue().encode("utf-8")
        output.seek(0)
        output.truncate(0)

        # Paginate through all transactions
        cursor = None
        while True:
            result = await list_transactions(current_user.tenant_id, limit=100, cursor=cursor)
            items = result["items"]
            
            for item in items:
                writer.writerow([
                    item.get("transactionId", ""),
                    item.get("provider", ""),
                    item.get("providerTransactionId", ""),
                    item.get("amount", ""),
                    item.get("currency", ""),
                    item.get("status", ""),
                    item.get("customerId", ""),
                    item.get("createdAt", "")
                ])
                yield output.getvalue().encode("utf-8")
                output.seek(0)
                output.truncate(0)
                
            cursor = result["meta"]["cursor"]
            if not cursor:
                break

    return StreamingResponse(
        iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=transactions_export.csv"}
    )

