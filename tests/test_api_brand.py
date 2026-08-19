"""
Integration tests for the /brands CRUD endpoints and their role requirements.

Brand routes are protected by ``require_superadmin_or_admin_or_storekeeper``,
so sellers (and anonymous callers) must be rejected.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.brand import Brand


# --------------------------------------------------------------------------- #
# POST /brands/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_brand_success(client, store_keeper_user, auth_headers):
    resp = await client.post(
        "/brands/", json={"name": "Apple", "is_active": True},
        headers=auth_headers(store_keeper_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Apple"
    assert isinstance(data["id"], int)


@pytest.mark.asyncio
async def test_create_brand_requires_authentication(client):
    resp = await client.post("/brands/", json={"name": "Anonymous"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_brand_forbidden_for_seller(client, seller_user, auth_headers):
    resp = await client.post(
        "/brands/", json={"name": "Nope"},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_brand_empty_name_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/brands/", json={"name": ""}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_brand_name_too_long_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/brands/", json={"name": "x" * 256}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_brand_name_raises_integrity_error(db_session, create_brand):
    await create_brand("Unique")
    db_session.add(Brand(name="Unique"))
    with pytest.raises(IntegrityError):
        await db_session.commit()


# --------------------------------------------------------------------------- #
# GET /brands/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_brands_returns_all_with_limit_zero(client, admin_user, auth_headers, create_brand):
    for idx in range(3):
        await create_brand(f"Brand {idx}")

    resp = await client.get(
        "/brands/", params={"limit": 0}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["size"] == 3  # limit is 0 -> all items
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_list_brands_respects_skip_and_limit(
    client, admin_user, auth_headers, create_brand
):
    for idx in range(5):
        await create_brand(f"Brand {idx}")

    resp = await client.get(
        "/brands/", params={"skip": 2, "limit": 2},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 5
    assert data["size"] == 2
    assert len(data["items"]) == 2
    # page = (skip // limit) + 1
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_list_brands_filter_by_active(client, admin_user, auth_headers, create_brand):
    await create_brand("Active One", is_active=True)
    await create_brand("Active Two", is_active=True)
    await create_brand("Retired", is_active=False)

    resp = await client.get(
        "/brands/", params={"is_active": "false"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    names = [item["name"] for item in resp.json()["items"]]
    assert names == ["Retired"]

    resp = await client.get(
        "/brands/", params={"is_active": "true"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


@pytest.mark.asyncio
async def test_list_brands_requires_authentication(client):
    resp = await client.get("/brands/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_brands_forbidden_for_seller(client, seller_user, auth_headers):
    resp = await client.get("/brands/", headers=auth_headers(seller_user))
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# GET /brands/{id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_brand_by_id(client, store_keeper_user, auth_headers, create_brand):
    brand = await create_brand("Target Brand")
    resp = await client.get(f"/brands/{brand.id}", headers=auth_headers(store_keeper_user))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Target Brand"


@pytest.mark.asyncio
async def test_get_brand_not_found(client, admin_user, auth_headers):
    resp = await client.get("/brands/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# PUT /brands/{id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_brand_success(client, super_admin_user, auth_headers, create_brand):
    brand = await create_brand("Old Name")
    resp = await client.put(
        f"/brands/{brand.id}", json={"name": "New Name", "is_active": False},
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_update_brand_not_found(client, admin_user, auth_headers):
    resp = await client.put(
        "/brands/999999", json={"name": "x"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_brand_empty_name_rejected(client, admin_user, auth_headers, create_brand):
    brand = await create_brand("Keep")
    resp = await client.put(
        f"/brands/{brand.id}", json={"name": ""}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# DELETE /brands/{id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_delete_brand_success(client, admin_user, auth_headers, create_brand):
    brand = await create_brand("Disposable")

    resp = await client.delete(f"/brands/{brand.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["message"] == "Brand deleted successfully"

    # The brand should now be gone.
    resp = await client.get(f"/brands/{brand.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_brand_not_found(client, admin_user, auth_headers):
    resp = await client.delete("/brands/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_brand_forbidden_for_seller(client, seller_user, auth_headers, create_brand):
    brand = await create_brand("Protected")
    resp = await client.delete(f"/brands/{brand.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 403