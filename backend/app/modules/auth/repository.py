"""Firestore repository for users, sessions, and password reset tokens."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import ulid

from app.infra.firestore import (
    collection,
    document,
    get_document,
    set_document,
    update_document,
    get_firestore_client,
    server_timestamp,
)

logger = logging.getLogger(__name__)

# ── Collection names ─────────────────────────────────────────────────────
USERS = "users"
AUTH_SESSIONS = "auth_sessions"
PASSWORD_RESET_TOKENS = "password_reset_tokens"


def generate_user_id() -> str:
    return f"u_{ulid.new().str.lower()}"


def generate_session_id() -> str:
    return f"s_{ulid.new().str.lower()}"


def generate_reset_token_id() -> str:
    return f"prt_{ulid.new().str.lower()}"


def hash_token(token: str) -> str:
    """SHA-256 hash of an opaque token for server-side storage."""
    return hashlib.sha256(token.encode()).hexdigest()


# ── User operations ──────────────────────────────────────────────────────

async def find_user_by_email(email_lower: str) -> dict[str, Any] | None:
    """Lookup user by normalized email. Returns raw dict or None."""
    coll = collection(USERS)
    query = coll.where("emailLower", "==", email_lower).limit(1)
    docs = []
    async for doc in query.stream():
        docs.append(doc.to_dict())
    return docs[0] if docs else None


async def get_user_by_id(user_id: str) -> dict[str, Any] | None:
    """Fetch user document by ID."""
    return await get_document(USERS, user_id)


async def create_user(user_data: dict[str, Any]) -> None:
    """Create a new user document."""
    user_data["createdAt"] = server_timestamp()
    await set_document(USERS, user_data["userId"], user_data)
    logger.info("Created user", extra={"userId": user_data["userId"]})


async def update_user(user_id: str, updates: dict[str, Any]) -> None:
    """Partially update user fields."""
    await update_document(USERS, user_id, updates)


# ── Session operations ───────────────────────────────────────────────────

async def create_session(session_data: dict[str, Any]) -> None:
    """Create a new auth session document."""
    session_data["createdAt"] = server_timestamp()
    session_data["lastSeenAt"] = server_timestamp()
    await set_document(AUTH_SESSIONS, session_data["sessionId"], session_data)
    logger.info("Created session", extra={"sessionId": session_data["sessionId"]})


async def get_session_by_id(session_id: str) -> dict[str, Any] | None:
    """Fetch session document by ID."""
    return await get_document(AUTH_SESSIONS, session_id)


async def update_session(session_id: str, updates: dict[str, Any]) -> None:
    """Partially update session fields."""
    await update_document(AUTH_SESSIONS, session_id, updates)


async def revoke_session(session_id: str, reason: str = "logout") -> None:
    """Mark a session as revoked."""
    await update_session(session_id, {
        "status": "revoked",
        "revokedAt": datetime.now(timezone.utc),
        "revokedReason": reason,
    })
    logger.info("Revoked session", extra={"sessionId": session_id})


async def revoke_all_user_sessions(
    user_id: str,
    reason: str = "logout_all",
    exclude_session_id: str | None = None,
) -> int:
    """Revoke all active sessions for a user. Returns count revoked."""
    coll = collection(AUTH_SESSIONS)
    query = coll.where("userId", "==", user_id).where("status", "==", "active")
    count = 0
    async for doc_snap in query.stream():
        if exclude_session_id and doc_snap.id == exclude_session_id:
            continue
        await revoke_session(doc_snap.id, reason)
        count += 1
    logger.info("Revoked all sessions", extra={"userId": user_id, "count": count})
    return count


async def list_user_sessions(user_id: str) -> list[dict[str, Any]]:
    """List all sessions for a user, ordered by creation desc."""
    coll = collection(AUTH_SESSIONS)
    query = (
        coll.where("userId", "==", user_id)
        .order_by("createdAt", direction="DESCENDING")
        .limit(50)
    )
    sessions = []
    async for doc_snap in query.stream():
        sessions.append(doc_snap.to_dict())
    return sessions


# ── Password reset token operations ──────────────────────────────────────

async def create_reset_token(token_data: dict[str, Any]) -> None:
    """Create a password reset token document."""
    token_data["createdAt"] = server_timestamp()
    await set_document(PASSWORD_RESET_TOKENS, token_data["tokenId"], token_data)


async def get_reset_token(token_id: str) -> dict[str, Any] | None:
    """Fetch reset token by ID."""
    return await get_document(PASSWORD_RESET_TOKENS, token_id)


async def mark_reset_token_used(token_id: str) -> None:
    """Mark reset token as used."""
    await update_document(PASSWORD_RESET_TOKENS, token_id, {
        "status": "used",
        "usedAt": datetime.now(timezone.utc),
    })
