"""
Integration tests for the /categories endpoints including role-based authorization.
"""
import pytest
from sqlalchemy import select

from app.models.category import Category


# --------------------------------------------------------------------------- #
# GET /categories/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_categories_authenticated(client, admin_user, auth_headers, create_category):
    await create_category("Electronics")
    await create_category("Stationery")
    resp = await client.get("/categories/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["skip"] == 0
    assert data["limit"] == 20
    assert [c["name"] for c in data["items"]] == ["Electronics", "Stationery"]


@pytest.mark.asyncio
async def test_list_categories_allows_seller(client, seller_user, auth_headers, create_category):
    await create_category("Toys")
    resp = await client.get("/categories/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert [c["name"] for c in resp.json()["items"]] == ["Toys"]


@pytest.mark.asyncio
async def test_list_categories_pagination(client, admin_user, auth_headers, create_category):
    for i in range(3):
        await create_category(f"Category {i}")

    resp = await client.get(
        "/categories/", params={"skip": 0, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert len(data["items"]) == 2

    resp = await client.get(
        "/categories/", params={"skip": 2, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_categories_unauthenticated(client):
    resp = await client.get("/categories/")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# POST /categories/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_category_by_admin(client, admin_user, auth_headers):
    resp = await client.post(
        "/categories/", json={"name": "Electronics"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Electronics"
    assert data["id"] is not None
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_create_category_by_superadmin(client, super_admin_user, auth_headers):
    resp = await client.post(
        "/categories/", json={"name": "Furniture"}, headers=auth_headers(super_admin_user)
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Furniture"


@pytest.mark.asyncio
async def test_create_category_forbidden_for_seller(client, seller_user, auth_headers):
    resp = await client.post(
        "/categories/", json={"name": "Toys"}, headers=auth_headers(seller_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_category_forbidden_for_store_keeper(client, store_keeper_user, auth_headers):
    resp = await client.post(
        "/categories/", json={"name": "Toys"}, headers=auth_headers(store_keeper_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_category_unauthenticated(client):
    resp = await client.post("/categories/", json={"name": "Toys"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_category_empty_name_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/categories/", json={"name": ""}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_category_name_too_long_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/categories/", json={"name": "x" * 51}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# GET /categories/{category_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_category_by_id(client, admin_user, auth_headers, create_category):
    category = await create_category("Electronics")
    resp = await client.get(f"/categories/{category.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == category.id
    assert data["name"] == "Electronics"


@pytest.mark.asyncio
async def test_get_category_by_id_allows_seller(client, seller_user, auth_headers, create_category):
    category = await create_category("Toys")
    resp = await client.get(f"/categories/{category.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Toys"


@pytest.mark.asyncio
async def test_get_category_not_found(client, admin_user, auth_headers):
    resp = await client.get("/categories/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_category_unauthenticated(client, create_category):
    category = await create_category("Electronics")
    resp = await client.get(f"/categories/{category.id}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# PUT /categories/{category_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_category_by_admin(client, db_session, admin_user, auth_headers, create_category):
    category = await create_category("Old Name")
    resp = await client.put(
        f"/categories/{category.id}",
        json={"name": "New Name"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == category.id
    assert data["name"] == "New Name"

    # Verify the existing row was updated in place (no duplicate row created).
    result = await db_session.execute(
        select(Category).where(Category.id == category.id)
    )
    updated = result.scalar_one()
    await db_session.refresh(updated)
    assert updated.name == "New Name"


@pytest.mark.asyncio
async def test_update_category_not_found(client, admin_user, auth_headers):
    resp = await client.put(
        "/categories/999999", json={"name": "Nope"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_category_forbidden_for_seller(client, seller_user, auth_headers, create_category):
    category = await create_category("Toys")
    resp = await client.put(
        f"/categories/{category.id}",
        json={"name": "Hacked"},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_category_unauthenticated(client, create_category):
    category = await create_category("Toys")
    resp = await client.put(f"/categories/{category.id}", json={"name": "New"})
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# DELETE /categories/{category_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_delete_category_by_admin(client, admin_user, auth_headers, create_category):
    category = await create_category("Electronics")
    resp = await client.delete(f"/categories/{category.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["message"] == "Category deleted successfully"

    resp = await client.get(f"/categories/{category.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_category_not_found(client, admin_user, auth_headers):
    resp = await client.delete("/categories/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_category_forbidden_for_seller(client, seller_user, auth_headers, create_category):
    category = await create_category("Toys")
    resp = await client.delete(f"/categories/{category.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_category_unauthenticated(client, create_category):
    category = await create_category("Toys")
    resp = await client.delete(f"/categories/{category.id}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_categories_empty_database(client, seller_user, auth_headers):
    resp = await client.get("/categories/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []