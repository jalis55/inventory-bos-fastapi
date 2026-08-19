"""
Additional integration tests for /auth covering role-restricted registration,
cookie behaviour, refresh-token rejection paths and rate limiting.
"""
import pytest

from app.core.config import settings
from app.models.user import Role
from app.utils.security import create_access_token, create_refresh_token
from tests.conftest import TEST_PASSWORD


# --------------------------------------------------------------------------- #
# /auth/register  -> role restrictions
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_register_seller_forbidden(client, seller_user, auth_headers):
    resp = await client.post(
        "/auth/register",
        json={"email": "x@example.com", "password": TEST_PASSWORD, "role": "seller"},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_register_admin_cannot_create_admin(client, admin_user, auth_headers):
    resp = await client.post(
        "/auth/register",
        json={"email": "newadmin@example.com", "password": TEST_PASSWORD, "role": "admin"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_register_admin_can_create_seller(client, admin_user, auth_headers):
    resp = await client.post(
        "/auth/register",
        json={"email": "newseller@example.com", "password": TEST_PASSWORD, "role": "seller"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["role"] == "seller"


@pytest.mark.asyncio
async def test_register_super_admin_cannot_create_super_admin(client, super_admin_user, auth_headers):
    resp = await client.post(
        "/auth/register",
        json={"email": "evil@example.com", "password": TEST_PASSWORD, "role": "super_admin"},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_register_defaults_to_seller_role(client, super_admin_user, auth_headers):
    resp = await client.post(
        "/auth/register",
        json={"email": "noRole@example.com", "password": TEST_PASSWORD},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["role"] == "seller"
    assert resp.json()["user"]["full_name"] is None


@pytest.mark.asyncio
async def test_register_invalid_email_rejected(client, super_admin_user, auth_headers):
    resp = await client.post(
        "/auth/register",
        json={"email": "not-an-email", "password": TEST_PASSWORD, "role": "seller"},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# POST /auth/login  -> cookies & edge cases
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_login_sets_http_only_cookies(client, create_user):
    await create_user("cookies@example.com", password=TEST_PASSWORD)
    resp = await client.post(
        "/auth/login", json={"email": "cookies@example.com", "password": TEST_PASSWORD}
    )
    assert resp.status_code == 200

    set_cookie_values = [v for k, v in resp.headers.multi_items() if k.lower() == "set-cookie"]
    assert len(set_cookie_values) == 2
    for value in set_cookie_values:
        assert "httponly" in value.lower()
        assert "path=/" in value.lower()
    # Access cookie covers the whole site, the refresh cookie only /auth/refresh.
    assert any("path=/auth/refresh" in v.lower() for v in set_cookie_values)


@pytest.mark.asyncio
async def test_login_inactive_user_raises_403(client, create_user):
    await create_user("sleeping@example.com", password=TEST_PASSWORD, is_active=False)
    resp = await client.post(
        "/auth/login", json={"email": "sleeping@example.com", "password": TEST_PASSWORD}
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_rate_limiter_blocks_excess_requests(client):
    for _ in range(5):
        resp = await client.post(
            "/auth/login", json={"email": "spam@example.com", "password": "WrongPass1!"}
        )
        assert resp.status_code == 401

    sixth = await client.post(
        "/auth/login", json={"email": "spam@example.com", "password": "WrongPass1!"}
    )
    assert sixth.status_code == 429


# --------------------------------------------------------------------------- #
# GET /auth/me  -> token sources & validity
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_me_authenticated_via_cookie_after_login(client, create_user):
    await create_user("cookieuser@example.com", password=TEST_PASSWORD)
    login = await client.post(
        "/auth/login", json={"email": "cookieuser@example.com", "password": TEST_PASSWORD}
    )
    assert login.status_code == 200

    resp = await client.get("/auth/me")  # no Authorization header
    assert resp.status_code == 200
    assert resp.json()["email"] == "cookieuser@example.com"


@pytest.mark.asyncio
async def test_me_rejects_refresh_token_in_access_slot(client, create_user):
    user = await create_user("ref@example.com")
    refresh = create_refresh_token({"sub": user.email})
    client.cookies.set(settings.ACCESS_COOKIE_NAME, refresh)
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_garbage_bearer_token(client):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# POST /auth/refresh
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_refresh_rejects_access_token_in_refresh_cookie(client, create_user):
    user = await create_user("acc@example.com")
    access = create_access_token({"sub": user.email, "role": user.role})
    client.cookies.set(settings.REFRESH_COOKIE_NAME, access, path="/auth/refresh")
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_garbage_token(client):
    client.cookies.set(settings.REFRESH_COOKIE_NAME, "garbage.token.value", path="/auth/refresh")
    resp = await client.post("/auth/refresh")
    assert resp.status_code == 401