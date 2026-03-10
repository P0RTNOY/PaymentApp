"""FastAPI application factory and middleware setup."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.auth import router as auth_router, me_router
from app.api.transactions import router as transactions_router
from app.config import get_settings
from app.config.logging import (
    setup_logging,
    request_id_var,
    tenant_id_var,
    user_id_var,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — setup and teardown."""
    settings = get_settings()
    setup_logging(level="DEBUG" if settings.environment == "local" else "INFO")
    logger.info(
        "Application starting",
        extra={
            "environment": settings.environment,
            "version": settings.api_version,
        },
    )
    yield
    logger.info("Application shutting down")


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Unified Payment App API",
        description="Payment collection orchestration and receipt management",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Rate Limiting ────────────────────────────────────────────────
    from slowapi.errors import RateLimitExceeded
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.middleware import SlowAPIMiddleware
    from app.config.rate_limit import limiter

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # ── Request ID middleware ────────────────────────────────────────
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next) -> Response:  # type: ignore[no-untyped-def]
        """Inject request ID and clear context vars per request."""
        req_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        token_rid = request_id_var.set(req_id)
        token_tid = tenant_id_var.set(None)
        token_uid = user_id_var.set(None)
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-Id"] = req_id
            return response
        finally:
            request_id_var.reset(token_rid)
            tenant_id_var.reset(token_tid)
            user_id_var.reset(token_uid)

    # ── Global exception handler ─────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unhandled exceptions — returns a clean 500."""
        req_id = request_id_var.get() or "unknown"
        logger.exception("Unhandled exception", extra={"errorCode": "internal.unexpected"})
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal.unexpected",
                    "message": "An unexpected error occurred.",
                },
                "meta": {"requestId": req_id},
            },
        )

    # ── Routers ──────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(transactions_router)
    
    from app.api.paybox import router as paybox_router
    app.include_router(paybox_router)
    
    from app.api.documents import router as documents_router, worker_router
    app.include_router(documents_router)
    app.include_router(worker_router)

    return app


# Uvicorn entrypoint
app = create_app()
