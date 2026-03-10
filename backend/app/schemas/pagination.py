"""Cursor-based pagination models for list endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""

    cursor: str | None = Field(None, description="Opaque cursor from previous response")
    limit: int = Field(20, ge=1, le=100, description="Number of items to return")


class PaginationMeta(BaseModel):
    """Pagination metadata returned with list responses."""

    next_cursor: str | None = Field(None, alias="nextCursor")
    has_more: bool = Field(False, alias="hasMore")

    model_config = {"populate_by_name": True}
