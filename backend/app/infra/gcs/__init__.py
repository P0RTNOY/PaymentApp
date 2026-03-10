"""Cloud Storage helpers for raw payload archival and document storage."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from google.cloud import storage  # type: ignore[attr-defined]

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: storage.Client | None = None


def get_storage_client() -> storage.Client:
    """Return a cached synchronous Cloud Storage client."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = storage.Client(project=settings.project_id)
        logger.info("Cloud Storage client initialised")
    return _client


# ── Raw Payload Archival ─────────────────────────────────────────────────

def build_raw_payload_path(
    provider_type: str,
    tenant_id: str | None,
    source: str,
    connection_id: str | None,
    event_id: str,
) -> str:
    """Build a GCS object path following the spec archival format.

    Format: raw/provider={type}/tenant={id}/date=YYYY-MM-DD/
            source={webhook|poll}/connection={id}/event={id}.json
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return (
        f"raw/provider={provider_type}/"
        f"tenant={tenant_id or 'unknown'}/"
        f"date={today}/"
        f"source={source}/"
        f"connection={connection_id or 'unknown'}/"
        f"event={event_id}.json"
    )


async def archive_raw_payload(
    bucket_name: str,
    path: str,
    payload: dict[str, Any],
) -> str:
    """Upload a JSON payload to Cloud Storage and return the full gs:// URI.

    This is intentionally synchronous under the hood because the
    google-cloud-storage SDK is sync. For MVP volume this is acceptable.
    """
    client = get_storage_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(path)
    blob.upload_from_string(
        json.dumps(payload, default=str),
        content_type="application/json",
    )
    uri = f"gs://{bucket_name}/{path}"
    logger.info("Archived raw payload", extra={"path": uri})
    return uri


async def upload_file(
    destination_path: str,
    content: bytes | str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload binary data and return the gs:// URI."""
    client = get_storage_client()
    settings = get_settings()
    bucket_name = settings.gcs_bucket_name
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_path)
    blob.upload_from_string(content, content_type=content_type)
    return f"gs://{bucket_name}/{destination_path}"


async def get_signed_download_url(
    path: str,
    expiration_minutes: int = 15,
) -> str:
    """Generate a short-lived signed download URL."""
    client = get_storage_client()
    settings = get_settings()
    bucket = client.bucket(settings.gcs_bucket_name)
    blob = bucket.blob(path)
    url = blob.generate_signed_url(
        expiration=timedelta(minutes=expiration_minutes),
        method="GET",
    )
    return url
