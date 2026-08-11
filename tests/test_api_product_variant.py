"""
Integration tests for the /product-variants endpoints including role-based authorization.
"""
import pytest

from app.models.product_variant import ProductVariant


# --------------------------------------------------------------------------- #
# GET /product-variants/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_product_variants_authenticated(client, admin_user, auth_headers, create_product_variant):
    await create_product_variant("Small")
    await create_product_variant("Large")
    resp = await client.get("/product-variants/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["skip"] == 0
    assert data["limit"] == 20
    assert [v["name"] for v in data["items"]] == ["Small", "Large"]


@pytest.mark.asyncio
async def test_list_product_variants_allows_seller(client, seller_user, auth_headers, create_product_variant):
    await create_product_variant("Medium")
    resp = await client.get("/product-variants/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert [v["name"] for v in resp.json()["items"]] == ["Medium"]


@pytest.mark.asyncio
async def test_list_product_variants_pagination(client, admin_user, auth_headers, create_product_variant):
    for i in range(3):
        await create_product_variant(f"Variant {i}")

    resp = await client.get(
        "/product-variants/", params={"skip": 0, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert len(data["items"]) == 2

    resp = await client.get(
        "/product-variants/", params={"skip": 2, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_product_variants_empty_database(client, seller_user, auth_headers):
    resp = await client.get("/product-variants/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_product_variants_unauthenticated(client):
    resp = await client.get("/product-variants/")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# POST /product-variants/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_product_variant_by_admin(client, admin_user, auth_headers):
    resp = await client.post(
        "/product-variants/", json={"name": "Small"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Small"
    assert data["id"] is not None
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_create_product_variant_by_superadmin(client, super_admin_user, auth_headers):
    resp = await client.post(
        "/product-variants/", json={"name": "Large"}, headers=auth_headers(super_admin_user)
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Large"


@pytest.mark.asyncio
async def test_create_product_variant_forbidden_for_seller(client, seller_user, auth_headers):
    resp = await client.post(
        "/product-variants/", json={"name": "Small"}, headers=auth_headers(seller_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_product_variant_forbidden_for_store_keeper(client, store_keeper_user, auth_headers):
    resp = await client.post(
        "/product-variants/", json={"name": "Small"}, headers=auth_headers(store_keeper_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_product_variant_unauthenticated(client):
    resp = await client.post("/product-variants/", json={"name": "Small"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_product_variant_empty_name_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/product-variants/", json={"name": ""}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_product_variant_name_too_long_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/product-variants/", json={"name": "x" * 51}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422
# --------------------------------------------------------------------------- #
# GET /product-variants/{variant_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_product_variant_by_id(client, admin_user, auth_headers, create_product_variant):
    variant = await create_product_variant("Small")
    resp = await client.get(f"/product-variants/{variant.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == variant.id
    assert data["name"] == "Small"


@pytest.mark.asyncio
async def test_get_product_variant_by_id_allows_seller(client, seller_user, auth_headers, create_product_variant):
    variant = await create_product_variant("Medium")
    resp = await client.get(f"/product-variants/{variant.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Medium"


@pytest.mark.asyncio
async def test_get_product_variant_not_found(client, admin_user, auth_headers):
    resp = await client.get("/product-variants/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_product_variant_unauthenticated(client, create_product_variant):
    variant = await create_product_variant("Small")
    resp = await client.get(f"/product-variants/{variant.id}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# PUT /product-variants/{variant_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_product_variant_by_admin(client, admin_user, auth_headers, create_product_variant):
    variant = await create_product_variant("Small")
    resp = await client.put(
        f"/product-variants/{variant.id}",
        json={"name": "Extra Small"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == variant.id
    assert data["name"] == "Extra Small"


@pytest.mark.asyncio
async def test_update_product_variant_not_found(client, admin_user, auth_headers):
    resp = await client.put(
        "/product-variants/999999", json={"name": "Nope"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_product_variant_forbidden_for_seller(client, seller_user, auth_headers, create_product_variant):
    variant = await create_product_variant("Small")
    resp = await client.put(
        f"/product-variants/{variant.id}",
        json={"name": "Hacked"},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_product_variant_unauthenticated(client, create_product_variant):
    variant = await create_product_variant("Small")
    resp = await client.put(f"/product-variants/{variant.id}", json={"name": "New"})
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# DELETE /product-variants/{variant_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_delete_product_variant_by_admin(client, admin_user, auth_headers, create_product_variant):
    variant = await create_product_variant("Small")
    resp = await client.delete(f"/product-variants/{variant.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["message"] == "Product variant deleted successfully"

    resp = await client.get(f"/product-variants/{variant.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_product_variant_not_found(client, admin_user, auth_headers):
    resp = await client.delete("/product-variants/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_product_variant_forbidden_for_seller(client, seller_user, auth_headers, create_product_variant):
    variant = await create_product_variant("Small")
    resp = await client.delete(f"/product-variants/{variant.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_product_variant_unauthenticated(client, create_product_variant):
    variant = await create_product_variant("Small")
    resp = await client.delete(f"/product-variants/{variant.id}")
    assert resp.status_code == 401