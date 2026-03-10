"""Argon2id password hashing utilities."""

from __future__ import annotations

import logging

from argon2 import PasswordHasher, Type as Argon2Type
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.config import get_settings

logger = logging.getLogger(__name__)

_hasher: PasswordHasher | None = None

# Current hash version — bump when changing parameters
PASSWORD_HASH_VERSION = 1


def _get_hasher() -> PasswordHasher:
    """Return a cached Argon2id password hasher with configured parameters."""
    global _hasher
    if _hasher is None:
        settings = get_settings()
        _hasher = PasswordHasher(
            time_cost=settings.password_hash_time_cost,
            memory_cost=settings.password_hash_memory_cost,
            parallelism=settings.password_hash_parallelism,
            type=Argon2Type.ID,
        )
    return _hasher


def hash_password(password: str) -> str:
    """Hash a plaintext password with Argon2id.

    Returns the full hash string including algorithm parameters and salt.
    """
    return _get_hasher().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash.

    Returns True if the password matches, False otherwise.
    Never raises on mismatch — only returns False.
    """
    try:
        return _get_hasher().verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Check whether the hash needs to be re-hashed with updated parameters.

    Call this on successful login to transparently upgrade old hashes.
    """
    try:
        return _get_hasher().check_needs_rehash(password_hash)
    except Exception:
        return True
