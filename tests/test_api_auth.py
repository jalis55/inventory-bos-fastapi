"""
Integration tests for the /auth endpoints via the FastAPI HTTP client.
"""
import pytest

from app.core.config import settings
from app.models.user import Role
from app.utils.security import create_refresh_token


# --------------------------------------------------------------------------- #
# /auth/register
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_register_creates_user(client, super_admin_user, auth_headers):
    payload = {
        "email": "newuser@example.com",
        "password": "Str0ng@Pass1",
        "full_name": "New User",
        "role": "admin",
    }
    resp = await client.post("/auth/register", json=payload, headers=auth_headers(super_admin_user))
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == "newuser@example.com"
    assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_register_requires_authentication(client):
    payload = {"email": "anon@example.com", "password": "password123", "role": "seller"}
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate_email(client, super_admin_user, auth_headers, create_user):
    await create_user("dup@example.com", role=Role.SELLER)
    payload = {"email": "dup@example.com", "password": "Str0ng@Pass1", "role": "seller"}
    resp = await client.post("/auth/register", json=payload, headers=auth_headers(super_admin_user))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_register_weak_password_validation_error(client, super_admin_user, auth_headers):
    payload = {"email": "weak@example.com", "password": "short", "role": "seller"}
    resp = await client.post("/auth/register", json=payload, headers=auth_headers(super_admin_user))
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# /auth/login
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_login_success_sets_cookies(client, create_user):
    await create_user("login@example.com", password="password123")
    resp = await client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    assert settings.ACCESS_COOKIE_NAME in resp.cookies
    assert settings.REFRESH_COOKIE_NAME in resp.cookies
    assert resp.json()["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, create_user):
    await create_user("bad@example.com", password="password123")
    resp = await client.post(
        "/auth/login",
        json={"email": "bad@example.com", "password": "wrongpass"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    resp = await client.post(
        "/auth/login",
        json={"email": "ghost@example.com", "password": "password123"},
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# /auth/refresh
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_refresh_issues_new_access_token(client, create_user):
    user = await create_user("refresh@example.com", password="password123")
    refresh = create_refresh_token({"sub": user.email})
    client.cookies.set(settings.REFRESH_COOKIE_NAME, refresh, path="/auth/refresh")
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200
    assert resp.json().get("access_token")


@pytest.mark.asyncio
async def test_refresh_missing_token(client):
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# /auth/logout
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_logout_clears_auth(client, create_user):
    await create_user("logout@example.com", password="password123")
    await client.post(
        "/auth/login",
        json={"email": "logout@example.com", "password": "password123"},
    )
    resp = await client.post("/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Successfully logged out"


# --------------------------------------------------------------------------- #
# /auth/me
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_me_authenticated(client, super_admin_user, auth_headers):
    resp = await client.get("/auth/me", headers=auth_headers(super_admin_user))
    assert resp.status_code == 200
    assert resp.json()["email"] == super_admin_user.email


@pytest.mark.asyncio
async def test_me_unauthenticated(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401
