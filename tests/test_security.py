"""
Unit tests for the security helpers (password hashing, JWT, cookies).
These do not need a database.
"""
from datetime import timedelta

from jose import jwt
from fastapi import Response

from app.core.config import settings
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    set_auth_cookies,
    clear_auth_cookies,
)


# --------------------------------------------------------------------------- #
# Password hashing
# --------------------------------------------------------------------------- #
def test_hash_and_verify_password():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


# --------------------------------------------------------------------------- #
# Token creation / decoding
# --------------------------------------------------------------------------- #
def test_create_access_token_contains_expected_claims():
    token = create_access_token({"sub": "a@b.com", "role": "admin"})
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "a@b.com"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_refresh_token_has_expected_type():
    token = create_refresh_token({"sub": "a@b.com"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["type"] == "refresh"
    assert payload["sub"] == "a@b.com"


def test_decode_token_valid_roundtrip():
    token = create_access_token({"sub": "a@b.com"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "a@b.com"


def test_decode_token_garbage_returns_none():
    assert decode_token("not.a.jwt") is None


def test_decode_token_tampered_returns_none():
    token = create_access_token({"sub": "a@b.com"})
    parts = token.split(".")
    parts[1] = "A" * len(parts[1])
    assert decode_token(".".join(parts)) is None


def test_decode_token_expired_returns_none():
    token = create_access_token({"sub": "a@b.com"}, expires_delta=timedelta(seconds=-1))
    assert decode_token(token) is None


# --------------------------------------------------------------------------- #
# Cookie helpers
# --------------------------------------------------------------------------- #
def test_set_auth_cookies_sets_both():
    resp = Response()
    set_auth_cookies(resp, "access-tok", "refresh-tok")
    cookies = "\n".join(resp.headers.getlist("set-cookie"))
    assert settings.ACCESS_COOKIE_NAME in cookies
    assert settings.REFRESH_COOKIE_NAME in cookies
    assert "access-tok" in cookies
    assert "refresh-tok" in cookies


def test_clear_auth_cookies_clears_both():
    resp = Response()
    clear_auth_cookies(resp)
    cookies = "\n".join(resp.headers.getlist("set-cookie"))
    assert settings.ACCESS_COOKIE_NAME in cookies
    assert settings.REFRESH_COOKIE_NAME in cookies
