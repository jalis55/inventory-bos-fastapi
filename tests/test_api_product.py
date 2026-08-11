"""
Integration tests for the /products endpoints including role-based authorization.

Products reference a company, a category and a product variant, so tests that
exercise the create/update paths first persist those related entities via the
test factories.
"""
import pytest

from app.models.product import Product


def _product_payload(company_id: int, category_id: int, variant_id: int, **overrides):
    payload = {
        "name": "Laptop",
        "company_id": company_id,
        "category_id": category_id,
        "product_variant_id": variant_id,
        "unit_of_measure": "piece",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# GET /products/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_products_authenticated(
    client, admin_user, auth_headers, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    await create_product("Laptop", company.id, category.id, variant.id)
    await create_product("Phone", company.id, category.id, variant.id)

    resp = await client.get("/products/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["skip"] == 0
    assert data["limit"] == 20
    assert [p["name"] for p in data["items"]] == ["Laptop", "Phone"]


@pytest.mark.asyncio
async def test_list_products_allows_seller(
    client, seller_user, auth_headers, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    await create_product("Tablet", company.id, category.id, variant.id)

    resp = await client.get("/products/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert [p["name"] for p in resp.json()["items"]] == ["Tablet"]


@pytest.mark.asyncio
async def test_list_products_pagination(
    client, admin_user, auth_headers, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    for i in range(3):
        await create_product(f"Product {i}", company.id, category.id, variant.id)

    resp = await client.get(
        "/products/", params={"skip": 0, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert len(data["items"]) == 2

    resp = await client.get(
        "/products/", params={"skip": 2, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_products_empty_database(client, seller_user, auth_headers):
    resp = await client.get("/products/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_products_unauthenticated(client):
    resp = await client.get("/products/")
    assert resp.status_code == 401
# --------------------------------------------------------------------------- #
# POST /products/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_product_by_admin(
    client, admin_user, auth_headers, create_company, create_category, create_product_variant
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")

    resp = await client.post(
        "/products/",
        json=_product_payload(company.id, category.id, variant.id),
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Laptop"
    assert data["unit_of_measure"] == "piece"
    assert data["company"]["id"] == company.id
    assert data["category"]["id"] == category.id
    assert data["product_variant"]["id"] == variant.id
    assert data["id"] is not None
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_create_product_by_superadmin(
    client, super_admin_user, auth_headers, create_company, create_category, create_product_variant
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")

    resp = await client.post(
        "/products/",
        json=_product_payload(company.id, category.id, variant.id),
        headers=auth_headers(super_admin_user),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Laptop"


@pytest.mark.asyncio
async def test_create_product_forbidden_for_seller(client, seller_user, auth_headers):
    resp = await client.post(
        "/products/", json=_product_payload(1, 1, 1), headers=auth_headers(seller_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_product_forbidden_for_store_keeper(client, store_keeper_user, auth_headers):
    resp = await client.post(
        "/products/", json=_product_payload(1, 1, 1), headers=auth_headers(store_keeper_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_product_unauthenticated(client):
    resp = await client.post("/products/", json=_product_payload(1, 1, 1))
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_product_empty_name_rejected(
    client, admin_user, auth_headers, create_company, create_category, create_product_variant
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")

    resp = await client.post(
        "/products/",
        json=_product_payload(company.id, category.id, variant.id, name=""),
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_product_name_too_long_rejected(
    client, admin_user, auth_headers, create_company, create_category, create_product_variant
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")

    resp = await client.post(
        "/products/",
        json=_product_payload(company.id, category.id, variant.id, name="x" * 51),
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 422
# --------------------------------------------------------------------------- #
# GET /products/{product_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_product_by_id(
    client, admin_user, auth_headers, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)

    resp = await client.get(f"/products/{product.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == product.id
    assert data["name"] == "Laptop"
    assert data["company"]["name"] == "Acme Corp"
    assert data["category"]["name"] == "Electronics"
    assert data["product_variant"]["name"] == "Small"


@pytest.mark.asyncio
async def test_get_product_by_id_allows_seller(
    client, seller_user, auth_headers, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Tablet", company.id, category.id, variant.id)

    resp = await client.get(f"/products/{product.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Tablet"


@pytest.mark.asyncio
async def test_get_product_not_found(client, admin_user, auth_headers):
    resp = await client.get("/products/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_product_unauthenticated(
    client, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)

    resp = await client.get(f"/products/{product.id}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# PUT /products/{product_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_product_by_admin(
    client, admin_user, auth_headers, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)

    resp = await client.put(
        f"/products/{product.id}",
        json={"name": "UltraBook", "unit_of_measure": "unit"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == product.id
    assert data["name"] == "UltraBook"
    assert data["unit_of_measure"] == "unit"


@pytest.mark.asyncio
async def test_update_product_not_found(client, admin_user, auth_headers):
    resp = await client.put(
        "/products/999999", json={"name": "Nope"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_product_forbidden_for_seller(
    client, seller_user, auth_headers, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)

    resp = await client.put(
        f"/products/{product.id}",
        json={"name": "Hacked"},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_product_unauthenticated(
    client, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)

    resp = await client.put(f"/products/{product.id}", json={"name": "New"})
    assert resp.status_code == 401
# --------------------------------------------------------------------------- #
# DELETE /products/{product_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_delete_product_by_admin(
    client, admin_user, auth_headers, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)

    resp = await client.delete(f"/products/{product.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["message"] == "Product deleted successfully"

    resp = await client.get(f"/products/{product.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_product_not_found(client, admin_user, auth_headers):
    resp = await client.delete("/products/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_product_forbidden_for_seller(
    client, seller_user, auth_headers, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)

    resp = await client.delete(f"/products/{product.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_product_unauthenticated(
    client, create_company, create_category, create_product_variant, create_product
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)

    resp = await client.delete(f"/products/{product.id}")
    assert resp.status_code == 401