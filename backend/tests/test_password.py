"""Tests for password hashing utilities."""

from __future__ import annotations

from app.infra.auth.password import hash_password, verify_password, needs_rehash


def test_hash_and_verify_correct_password():
    """Correct password should verify successfully."""
    pw = "my-strong-P@ssword-123"
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True


def test_verify_wrong_password():
    """Wrong password should fail verification."""
    hashed = hash_password("correct-password")
    assert verify_password("wrong-password", hashed) is False


def test_hash_is_not_plaintext():
    """Hash should never be the plaintext password."""
    pw = "test-password"
    hashed = hash_password(pw)
    assert hashed != pw
    assert "$argon2" in hashed


def test_different_hashes_for_same_password():
    """Two hashes of the same password should differ (salted)."""
    pw = "same-password"
    h1 = hash_password(pw)
    h2 = hash_password(pw)
    assert h1 != h2


def test_needs_rehash_on_valid_hash():
    """A freshly created hash should not need rehashing."""
    hashed = hash_password("password")
    assert needs_rehash(hashed) is False


def test_needs_rehash_on_garbage():
    """Garbage input should report needing rehash."""
    assert needs_rehash("not-a-real-hash") is True
