"""Secret Manager access wrapper."""

from __future__ import annotations

import logging

from google.cloud import secretmanager  # type: ignore[attr-defined]

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: secretmanager.SecretManagerServiceClient | None = None


def get_secret_manager_client() -> secretmanager.SecretManagerServiceClient:
    """Return a cached Secret Manager client."""
    global _client
    if _client is None:
        _client = secretmanager.SecretManagerServiceClient()
        logger.info("Secret Manager client initialised")
    return _client


async def get_secret(secret_ref: str, version: str = "latest") -> str:
    """Fetch a secret value from Secret Manager.

    Parameters
    ----------
    secret_ref:
        Full resource name, e.g.
        ``projects/my-project/secrets/my-secret``
        or just the secret name (auto-prefixed with project).
    version:
        Secret version, defaults to ``"latest"``.

    Returns
    -------
    str
        The decoded payload string.
    """
    settings = get_settings()
    client = get_secret_manager_client()

    if not secret_ref.startswith("projects/"):
        secret_ref = f"projects/{settings.project_id}/secrets/{secret_ref}"

    name = f"{secret_ref}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    payload = response.payload.data.decode("utf-8")

    # Never log the actual secret value
    logger.debug("Accessed secret", extra={"secretRef": secret_ref})
    return payload


async def create_secret(secret_id: str, payload: str) -> str:
    """Create a new secret with an initial version.

    Returns the full secret resource name.
    """
    settings = get_settings()
    client = get_secret_manager_client()
    parent = f"projects/{settings.project_id}"

    # Create the secret
    secret = client.create_secret(
        request={
            "parent": parent,
            "secret_id": secret_id,
            "secret": {"replication": {"automatic": {}}},
        }
    )

    # Add the first version
    client.add_secret_version(
        request={
            "parent": secret.name,
            "payload": {"data": payload.encode("utf-8")},
        }
    )

    logger.info("Created secret", extra={"secretId": secret_id})
    return secret.name
