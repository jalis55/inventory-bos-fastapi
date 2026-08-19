"""
Additional integration tests for /users: role-based visibility, pagination,
update rules and password flows.
"""
import pytest

from app.core.config import settings
from app.models.user import Role
from tests.conftest import TEST_PASSWORD


# --------------------------------------------------------------------------- #
# GET /users/  -> role-visibility & pagination
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_users_super_admin_sees_admins_and_below(
    client, super_admin_user, auth_headers, create_user
):
    await create_user("adminb@example.com", role=Role.ADMIN)
    await create_user("sellerb@example.com", role=Role.SELLER)

    resp = await client.get("/users/", headers=auth_headers(super_admin_user))
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()["items"]]
    # Super admin sees admins and below, but never other super admins.
    assert "adminb@example.com" in emails
    assert "sellerb@example.com" in emails
    assert super_admin_user.email not in emails


@pytest.mark.asyncio
async def test_list_users_admin_does_not_see_admins(client, admin_user, auth_headers, create_user):
    await create_user("adminc@example.com", role=Role.ADMIN)
    await create_user("sellerc@example.com", role=Role.SELLER)

    resp = await client.get("/users/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()["items"]]
    assert "sellerc@example.com" in emails
    assert "adminc@example.com" not in emails


@pytest.mark.asyncio
async def test_list_users_pagination(client, admin_user, auth_headers, create_user):
    for idx in range(5):
        await create_user(f"pag{idx}@example.com", role=Role.SELLER)

    resp = await client.get(
        "/users/", params={"skip": 1, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["skip"] == 1
    assert data["limit"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_list_users_limit_out_of_range_rejected(client, admin_user, auth_headers):
    resp = await client.get("/users/", params={"limit": 101}, headers=auth_headers(admin_user))
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# GET /users/{user_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_user_super_admin_can_view_admin(client, super_admin_user, auth_headers, create_user):
    admin = await create_user("viewadmin@example.com", role=Role.ADMIN)
    resp = await client.get(f"/users/{admin.id}", headers=auth_headers(super_admin_user))
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_get_user_admin_cannot_view_other_admin(client, admin_user, auth_headers, create_user):
    other_admin = await create_user("otheradmin@example.com", role=Role.ADMIN)
    resp = await client.get(f"/users/{other_admin.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_user_admin_cannot_view_super_admin(client, admin_user, auth_headers, super_admin_user):
    resp = await client.get(f"/users/{super_admin_user.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_user_requires_privileges(client, seller_user, auth_headers, create_user):
    target = await create_user("target2@example.com", role=Role.SELLER)
    resp = await client.get(f"/users/{target.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# PUT /users/{user_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_user_super_admin_can_update_admin(client, super_admin_user, auth_headers, create_user):
    admin = await create_user("updadmin@example.com", role=Role.ADMIN)
    resp = await client.put(
        f"/users/{admin.id}", json={"full_name": "Renamed Admin"},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Renamed Admin"


@pytest.mark.asyncio
async def test_update_user_admin_cannot_update_super_admin(client, admin_user, auth_headers, super_admin_user):
    resp = await client.put(
        f"/users/{super_admin_user.id}", json={"full_name": "x"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_user_email_field_is_ignored(client, admin_user, auth_headers, create_user):
    # The UserUpdate schema does not include `email`, so addresses cannot be
    # changed through this endpoint. Sending one should be silently ignored.
    target = await create_user("orig@example.com", role=Role.SELLER)

    resp = await client.put(
        f"/users/{target.id}",
        json={"email": "changed@example.com", "full_name": "Renamed"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "orig@example.com"
    assert resp.json()["full_name"] == "Renamed"


@pytest.mark.asyncio
async def test_update_user_invalid_role_rejected(client, admin_user, auth_headers, create_user):
    target = await create_user("badrole@example.com", role=Role.SELLER)
    resp = await client.put(
        f"/users/{target.id}", json={"role": "emperor"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_user_not_found(client, admin_user, auth_headers):
    resp = await client.put(
        "/users/999999", json={"full_name": "nope"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_user_forbidden_for_store_keeper(client, store_keeper_user, auth_headers, create_user):
    target = await create_user("keepervictim@example.com", role=Role.SELLER)
    resp = await client.put(
        f"/users/{target.id}", json={"full_name": "hack"},
        headers=auth_headers(store_keeper_user),
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# POST /users/change-password
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_change_password_allows_login_with_new_password(client, create_user, auth_headers):
    user = await create_user("rotate@example.com", password=TEST_PASSWORD)

    resp = await client.post(
        "/users/change-password",
        json={
            "email": user.email,
            "old_password": TEST_PASSWORD,
            "new_password": "NewPassword123!",
        },
        headers=auth_headers(user),
    )
    assert resp.status_code == 200

    login = await client.post(
        "/auth/login", json={"email": user.email, "password": "NewPassword123!"}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_weak_new_password_rejected(client, seller_user, auth_headers):
    resp = await client.post(
        "/users/change-password",
        json={
            "email": seller_user.email,
            "old_password": "password123",
            "new_password": "short",
        },
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_change_password_requires_authentication(client):
    resp = await client.post(
        "/users/change-password",
        json={
            "email": "anyone@example.com",
            "old_password": "password123",
            "new_password": "NewPassword123!",
        },
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# POST /users/reset-password
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_reset_password_by_admin(client, admin_user, auth_headers, create_user):
    user = await create_user("adminresets@example.com", role=Role.SELLER)
    resp = await client.post(
        "/users/reset-password", params={"email": user.email},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["new_password"] == settings.DEFAULT_RESET_PASSWORD


@pytest.mark.asyncio
async def test_reset_password_admin_cannot_reset_admin(client, admin_user, auth_headers, create_user):
    other_admin = await create_user("adminreset@example.com", role=Role.ADMIN)
    resp = await client.post(
        "/users/reset-password", params={"email": other_admin.email},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reset_password_admin_cannot_reset_super_admin(client, admin_user, auth_headers, super_admin_user):
    resp = await client.post(
        "/users/reset-password", params={"email": super_admin_user.email},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reset_password_super_admin_can_reset_admin(client, super_admin_user, auth_headers, create_user):
    other_admin = await create_user("sareset@example.com", role=Role.ADMIN)
    resp = await client.post(
        "/users/reset-password", params={"email": other_admin.email},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["new_password"] == settings.DEFAULT_RESET_PASSWORD