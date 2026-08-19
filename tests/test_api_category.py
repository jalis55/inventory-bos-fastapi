"""
Integration tests for the /category endpoints.

Listing and fetching a category only require an authenticated user, while
create / update / delete are restricted to super admins, admins and store
keepers.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.category import Category


# --------------------------------------------------------------------------- #
# GET /category/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_categories_any_authenticated_user(client, seller_user, auth_headers, create_category):
    await create_category("Electronics")
    await create_category("Furniture")

    resp = await client.get("/category/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    names = [item["name"] for item in data["items"]]
    assert "Electronics" in names
    assert "Furniture" in names


@pytest.mark.asyncio
async def test_list_categories_requires_authentication(client):
    resp = await client.get("/category/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_categories_filter_by_active(client, admin_user, auth_headers, create_category):
    await create_category("Live One", is_active=True)
    await create_category("Dead One", is_active=False)

    resp = await client.get(
        "/category/", params={"is_active": "false"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert [i["name"] for i in data["items"]] == ["Dead One"]
    assert data["total"] == 1


@pytest.mark.asyncio
async def test_list_categories_pagination(client, admin_user, auth_headers, create_category):
    for idx in range(5):
        await create_category(f"Category {idx}")

    resp = await client.get(
        "/category/", params={"skip": 2, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["page"] == 2
    assert data["size"] == 2


# --------------------------------------------------------------------------- #
# POST /category/create
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_category_success(client, store_keeper_user, auth_headers):
    resp = await client.post(
        "/category/create", json={"name": "Electronics"},
        headers=auth_headers(store_keeper_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Electronics"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_category_requires_authentication(client):
    resp = await client.post("/category/create", json={"name": "Sneaky"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_category_forbidden_for_seller(client, seller_user, auth_headers):
    resp = await client.post(
        "/category/create", json={"name": "Nope"}, headers=auth_headers(seller_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_category_empty_name_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/category/create", json={"name": ""}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_category_name_raises_integrity_error(db_session, create_category):
    await create_category("UniqueCat")
    db_session.add(Category(name="UniqueCat"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


# --------------------------------------------------------------------------- #
# PUT /category/{id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_category_success(client, super_admin_user, auth_headers, create_category):
    category = await create_category("Old Category")
    resp = await client.put(
        f"/category/{category.id}", json={"name": "New Category", "is_active": False},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Category"
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_update_category_not_found(client, admin_user, auth_headers):
    resp = await client.put(
        "/category/999999", json={"name": "x"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_category_empty_name_rejected(client, admin_user, auth_headers, create_category):
    category = await create_category("Keep")
    resp = await client.put(
        f"/category/{category.id}", json={"name": ""}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_category_forbidden_for_seller(client, seller_user, auth_headers, create_category):
    category = await create_category("Protected")
    resp = await client.put(
        f"/category/{category.id}", json={"name": "hack"}, headers=auth_headers(seller_user)
    )
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# GET /category/{id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_category_by_id_any_authenticated_user(client, seller_user, auth_headers, create_category):
    category = await create_category("Target Category")
    resp = await client.get(f"/category/{category.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Target Category"


@pytest.mark.asyncio
async def test_get_category_not_found(client, seller_user, auth_headers):
    resp = await client.get("/category/999999", headers=auth_headers(seller_user))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# DELETE /category/{id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_delete_category_success(client, admin_user, auth_headers, create_category):
    category = await create_category("Disposable")

    resp = await client.delete(f"/category/{category.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["message"] == "Category deleted successfully"

    resp = await client.get(f"/category/{category.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_category_not_found(client, admin_user, auth_headers):
    resp = await client.delete("/category/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_category_forbidden_for_seller(client, seller_user, auth_headers, create_category):
    category = await create_category("Protected")
    resp = await client.delete(f"/category/{category.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 403