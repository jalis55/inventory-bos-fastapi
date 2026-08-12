"""
Integration tests for the supplier-return system.

Creating a supplier return atomically posts an OUT stock movement for each
returned line and deducts the batch balance. Returns are immutable: only POST
(create) and GET are exposed.
"""
import pytest


_supplier_seq = 0


async def _make_batch(
    create_company,
    create_category,
    create_product_variant,
    create_product,
    create_supplier,
    create_batch,
    quantity=200,
):
    global _supplier_seq
    _supplier_seq += 1
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)
    supplier = await create_supplier(
        f"Acme Supplies {_supplier_seq}", phone=f"011233{_supplier_seq:05d}"
    )
    batch = await create_batch(
        product.id, supplier.id, received_quantity=quantity, units_per_package=1
    )
    return supplier, batch


# --------------------------------------------------------------------------- #
# POST /supplier-returns/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_partial_return_posts_out_and_deducts_batch(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=200,
    )
    resp = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "reason": "expired",
            "items": [{"batch_id": batch.id, "quantity": 20}],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["return_number"].startswith("SR-")
    assert data["status"] == "completed"
    assert data["reason"] == "expired"
    assert len(data["items"]) == 1
    assert data["items"][0]["batch_id"] == batch.id
    assert data["items"][0]["quantity"] == 20

    # Batch balance deducted
    r = await client.get(f"/batches/{batch.id}", headers=auth_headers(admin_user))
    assert r.json()["quantity"] == 180

    # Ledger OUT movement recorded with supplier + reference
    r = await client.get(
        "/stock-movements/", params={"batch_id": batch.id},
        headers=auth_headers(admin_user),
    )
    movement = r.json()["items"][0]
    assert movement["movement_type"] == "out"
    assert movement["quantity"] == 20
    assert movement["prev_quantity"] == 200
    assert movement["current_quantity"] == 180
    assert movement["supplier_id"] == supplier.id
    assert movement["reference"] == data["return_number"]


@pytest.mark.asyncio
async def test_create_return_multiple_batches(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    company = await create_company("Corp")
    category = await create_category("Category")
    variant = await create_product_variant("Variant")
    supplier = await create_supplier("Single Supplier", phone="01123999999")
    product_a = await create_product("A", company.id, category.id, variant.id)
    product_b = await create_product("B", company.id, category.id, variant.id)
    batch1 = await create_batch(
        product_a.id, supplier.id, received_quantity=100, units_per_package=1
    )
    batch2 = await create_batch(
        product_b.id, supplier.id, received_quantity=50, units_per_package=1
    )
    resp = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "items": [
                {"batch_id": batch1.id, "quantity": 10},
                {"batch_id": batch2.id, "quantity": 5},
            ],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["items"]) == 2

    # Both batches deducted
    r = await client.get(f"/batches/{batch1.id}", headers=auth_headers(admin_user))
    assert r.json()["quantity"] == 90
    r = await client.get(f"/batches/{batch2.id}", headers=auth_headers(admin_user))
    assert r.json()["quantity"] == 45


@pytest.mark.asyncio
async def test_create_return_overdraw_rejected(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=10,
    )
    resp = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "items": [{"batch_id": batch.id, "quantity": 999}],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 400

    # Nothing changed: no return created, batch unchanged
    r = await client.get(f"/batches/{batch.id}", headers=auth_headers(admin_user))
    assert r.json()["quantity"] == 10
    r = await client.get("/supplier-returns/", headers=auth_headers(admin_user))
    assert r.json()["total"] == 0


@pytest.mark.asyncio
async def test_create_return_wrong_supplier_rejected(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    other = await create_supplier("Other Supplier", phone="01123888888")
    resp = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": other.id,
            "return_date": "2026-08-12",
            "items": [{"batch_id": batch.id, "quantity": 5}],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_return_batch_not_found(
    client, admin_user, auth_headers, create_supplier,
):
    supplier = await create_supplier("Sup", phone="01123777777")
    resp = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "items": [{"batch_id": 999999, "quantity": 5}],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_return_supplier_not_found(client, admin_user, auth_headers):
    resp = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": 999999,
            "return_date": "2026-08-12",
            "items": [{"batch_id": 1, "quantity": 5}],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_return_forbidden_for_seller(
    client, seller_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    resp = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "items": [{"batch_id": batch.id, "quantity": 5}],
        },
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_return_unauthenticated(
    client, create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    resp = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "items": [{"batch_id": batch.id, "quantity": 5}],
        },
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# GET /supplier-returns/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_supplier_returns_authenticated(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "reason": "expired",
            "items": [{"batch_id": batch.id, "quantity": 10}],
        },
        headers=auth_headers(admin_user),
    )
    resp = await client.get("/supplier-returns/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["reason"] == "expired"
    assert data["items"][0]["supplier"]["id"] == supplier.id
    assert len(data["items"][0]["items"]) == 1


@pytest.mark.asyncio
async def test_list_supplier_returns_unauthenticated(client):
    resp = await client.get("/supplier-returns/")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# GET /supplier-returns/{id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_supplier_return(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    created = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "items": [{"batch_id": batch.id, "quantity": 5}],
        },
        headers=auth_headers(admin_user),
    )
    return_id = created.json()["id"]

    resp = await client.get(
        f"/supplier-returns/{return_id}", headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == return_id


@pytest.mark.asyncio
async def test_get_supplier_return_not_found(client, admin_user, auth_headers):
    resp = await client.get("/supplier-returns/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Immutability: no update / delete routes exposed
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_supplier_return_not_allowed(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    created = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "items": [{"batch_id": batch.id, "quantity": 5}],
        },
        headers=auth_headers(admin_user),
    )
    return_id = created.json()["id"]
    resp = await client.put(
        f"/supplier-returns/{return_id}", json={"reason": "changed"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_delete_supplier_return_not_allowed(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    created = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "items": [{"batch_id": batch.id, "quantity": 5}],
        },
        headers=auth_headers(admin_user),
    )
    return_id = created.json()["id"]
    resp = await client.delete(
        f"/supplier-returns/{return_id}", headers=auth_headers(admin_user)
    )
    assert resp.status_code == 405

