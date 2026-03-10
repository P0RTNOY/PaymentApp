"""Standard API response envelope models per spec conventions."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ── Meta ─────────────────────────────────────────────────────────────────

class ResponseMeta(BaseModel):
    """Metadata included in every API response."""

    request_id: str = Field(..., alias="requestId")

    model_config = {"populate_by_name": True}


# ── Success Envelope ─────────────────────────────────────────────────────

class ApiResponse(BaseModel, Generic[T]):
    """Standard success response: ``{ data: T, meta: {...} }``."""

    data: T
    meta: ResponseMeta


# ── Error Detail ─────────────────────────────────────────────────────────

class ErrorDetail(BaseModel):
    """Structured error body."""

    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiErrorResponse(BaseModel):
    """Standard error response: ``{ error: {...}, meta: {...} }``."""

    error: ErrorDetail
    meta: ResponseMeta
