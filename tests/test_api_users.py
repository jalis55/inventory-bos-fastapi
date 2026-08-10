"""
Integration tests for the /users endpoints including role-based authorization.
"""
import pytest

from app.core.config import settings
from app.models.user import Role


# --------------------------------------------------------------------------- #
# GET /users/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_users_admin(client, admin_user, auth_headers, create_user):
    await create_user("someone@example.com", role=Role.SELLER)
    resp = await client.get("/users/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data["items"]]
    assert "someone@example.com" in emails
    assert admin_user.email in emails


@pytest.mark.asyncio
async def test_list_users_forbidden_for_seller(client, seller_user, auth_headers):
    resp = await client.get("/users/", headers=auth_headers(seller_user))
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# GET /users/{user_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_user_by_id(client, admin_user, auth_headers, create_user):
    user = await create_user("target@example.com", role=Role.SELLER)
    resp = await client.get(f"/users/{user.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["email"] == "target@example.com"


@pytest.mark.asyncio
async def test_get_user_not_found(client, admin_user, auth_headers):
    resp = await client.get("/users/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# POST /users/change-password
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_change_password_success(client, seller_user, auth_headers):
    resp = await client.post(
        "/users/change-password",
        json={
            "email": seller_user.email,
            "old_password": "password123",
            "new_password": "NewStr0ng@123",
        },
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "Password changed successfully"


@pytest.mark.asyncio
async def test_change_password_wrong_old_password(client, seller_user, auth_headers):
    resp = await client.post(
        "/users/change-password",
        json={
            "email": seller_user.email,
            "old_password": "wrong-old",
            "new_password": "NewStr0ng@123",
        },
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# PUT /users/{user_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_user_success(client, admin_user, auth_headers, create_user):
    user = await create_user("upd@example.com", role=Role.SELLER)
    resp = await client.put(
        f"/users/{user.id}", json={"full_name": "Updated"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated"


@pytest.mark.asyncio
async def test_update_own_account_forbidden(client, admin_user, auth_headers):
    resp = await client.put(
        f"/users/{admin_user.id}", json={"full_name": "nope"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_another_admin_forbidden(client, admin_user, auth_headers, create_user):
    other_admin = await create_user("admin2@example.com", role=Role.ADMIN)
    resp = await client.put(
        f"/users/{other_admin.id}", json={"full_name": "x"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_user_forbidden_for_seller(client, seller_user, auth_headers, create_user):
    user = await create_user("victim@example.com", role=Role.SELLER)
    resp = await client.put(
        f"/users/{user.id}", json={"full_name": "hack"},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# POST /users/reset-password
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_reset_password_by_superadmin(client, super_admin_user, auth_headers, create_user):
    user = await create_user("reset@example.com", role=Role.SELLER)
    resp = await client.post(
        "/users/reset-password",
        params={"email": user.email},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["new_password"] == settings.DEFAULT_RESET_PASSWORD


@pytest.mark.asyncio
async def test_reset_password_forbidden_for_seller(client, seller_user, auth_headers, create_user):
    user = await create_user("victim2@example.com", role=Role.SELLER)
    resp = await client.post(
        "/users/reset-password",
        params={"email": user.email},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reset_password_user_not_found(client, super_admin_user, auth_headers):
    resp = await client.post(
        "/users/reset-password",
        params={"email": "missing@example.com"},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 404
