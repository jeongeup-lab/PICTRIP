"""Unit tests for password hashing helpers (app.core.passwords)."""

from __future__ import annotations

from app.core.passwords import hash_password, verify_password


def test_hash_password_is_not_plaintext() -> None:
    hashed = hash_password("hunter2-secret")
    assert hashed != "hunter2-secret"
    assert hashed.startswith("$2")  # bcrypt prefix


def test_verify_password_roundtrip() -> None:
    hashed = hash_password("correct horse battery")
    assert verify_password("correct horse battery", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_password_handles_none_hash() -> None:
    assert verify_password("anything", None) is False


def test_hash_password_handles_long_input() -> None:
    # bcrypt has a 72-byte input limit; the helper must not raise on long input.
    long_pw = "a" * 200
    hashed = hash_password(long_pw)
    assert verify_password(long_pw, hashed) is True
