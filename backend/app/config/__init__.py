"""Application settings loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the Payment App backend.

    All values can be overridden via environment variables.
    Prefix is ``APP_`` (e.g. ``APP_PROJECT_ID``).
    """

    model_config = {"env_prefix": "APP_", "case_sensitive": False}

    # ── GCP ──────────────────────────────────────────────────────────────
    project_id: str = "payment-app-local"
    environment: str = "local"  # local | staging | production

    # ── API ──────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_version: str = "v1"
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ── Auth / JWT ───────────────────────────────────────────────────────
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # ── Firestore ────────────────────────────────────────────────────────
    firestore_database: str = "(default)"

    # ── Cloud Storage ────────────────────────────────────────────────────
    gcs_raw_payload_bucket: str = "payment-app-raw-payloads"
    gcs_documents_bucket: str = "payment-app-documents"

    # ── Cloud Tasks ──────────────────────────────────────────────────────
    cloud_tasks_location: str = "me-west1"
    cloud_tasks_sync_queue: str = "provider-sync"
    cloud_tasks_document_queue: str = "document-issuance"
    cloud_tasks_validation_queue: str = "provider-validation"

    # ── Pub/Sub ──────────────────────────────────────────────────────────
    pubsub_transaction_topic: str = "transaction-events"

    # ── Password hashing ─────────────────────────────────────────────────
    password_hash_time_cost: int = 3
    password_hash_memory_cost: int = 65536  # 64 MiB
    password_hash_parallelism: int = 4

    # ── Rate limiting ────────────────────────────────────────────────────
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15

    # ── Service URLs (for Cloud Tasks targets) ───────────────────────────
    worker_service_url: str = "http://localhost:8001"
    api_service_url: str = "http://localhost:8000"


# ── Singleton ────────────────────────────────────────────────────────────
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
