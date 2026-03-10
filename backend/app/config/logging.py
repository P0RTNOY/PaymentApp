"""Structured JSON logging for Cloud Run / Cloud Logging compatibility."""

from __future__ import annotations

import logging
import json
import sys
from contextvars import ContextVar
from typing import Any

# ── Context vars for request-scoped correlation ──────────────────────────
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


class StructuredJsonFormatter(logging.Formatter):
    """Formats log records as JSON objects per Cloud Logging conventions.

    Includes contextual fields (requestId, tenantId, etc.) when available.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
        }

        # Inject context vars if set
        if (rid := request_id_var.get()) is not None:
            log_entry["requestId"] = rid
        if (cid := correlation_id_var.get()) is not None:
            log_entry["correlationId"] = cid
        if (tid := tenant_id_var.get()) is not None:
            log_entry["tenantId"] = tid
        if (uid := user_id_var.get()) is not None:
            log_entry["userId"] = uid

        # Extra fields from record
        for key in ("providerType", "providerConnectionId", "transactionId",
                     "documentId", "syncRunId", "taskName", "eventType",
                     "errorCode", "latencyMs"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        # Exception info
        if record.exc_info and record.exc_info[1]:
            log_entry["error"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        return json.dumps(log_entry, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with structured JSON output to stderr."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(StructuredJsonFormatter())
    root.addHandler(handler)

    # Silence noisy third-party loggers
    for name in ("google", "urllib3", "httpx", "httpcore", "grpc"):
        logging.getLogger(name).setLevel(logging.WARNING)
