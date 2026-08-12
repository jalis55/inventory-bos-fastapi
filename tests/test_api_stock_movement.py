"""
Integration tests for the /stock-movements endpoints.

Stock movements are immutable, bank-ledger style entries: only POST (create)
and GET are exposed. Creating a movement atomically adjusts the parent batch
balance; an OUT that would drive the balance below zero is rejected.
"""
import pytest

from app.models.stock_movement import MovementType

_supplier_seq = 0


async def _make_batch(
    create_company,
    create_category,
    create_product_variant,
    create_product,
    create_supplier,
    create_batch,
    quantity=100,
):
    global _supplier_seq
    _supplier_seq += 1
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)
    supplier = await create_supplier(
        f"Acme Supplies {_supplier_seq}", phone=f"011234{_supplier_seq:05d}"
    )
    batch = await create_batch(
        product.id, supplier.id, received_quantity=quantity, units_per_package=1
    )
    return batch


# --------------------------------------------------------------------------- #
# POST /stock-movements/ (create)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_in_increases_batch_quantity(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    resp = await client.post(
        "/stock-movements/",
        json={"batch_id": batch.id, "movement_type": "in", "quantity": 50},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["movement_type"] == "in"
    assert data["quantity"] == 50
    assert data["prev_quantity"] == 100
    assert data["current_quantity"] == 150

    # Batch balance follows the ledger
    resp = await client.get(f"/batches/{batch.id}", headers=auth_headers(admin_user))
    assert resp.json()["quantity"] == 150


@pytest.mark.asyncio
async def test_create_out_decreases_batch_quantity(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    resp = await client.post(
        "/stock-movements/",
        json={"batch_id": batch.id, "movement_type": "out", "quantity": 40},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["prev_quantity"] == 100
    assert data["current_quantity"] == 60

    resp = await client.get(f"/batches/{batch.id}", headers=auth_headers(admin_user))
    assert resp.json()["quantity"] == 60


@pytest.mark.asyncio
async def test_create_out_overdraw_rejected(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=10,
    )
    resp = await client.post(
        "/stock-movements/",
        json={"batch_id": batch.id, "movement_type": "out", "quantity": 999},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 400

    # No movement written and balance unchanged
    resp = await client.get(f"/batches/{batch.id}", headers=auth_headers(admin_user))
    assert resp.json()["quantity"] == 10


@pytest.mark.asyncio
async def test_reversal_entry_restores_balance(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    # Record an OUT, then a reversing IN (bank-style correction)
    out = await client.post(
        "/stock-movements/",
        json={"batch_id": batch.id, "movement_type": "out", "quantity": 30,
              "reference": "Mistake"},
        headers=auth_headers(admin_user),
    )
    assert out.status_code == 201
    out_id = out.json()["id"]

    back = await client.post(
        "/stock-movements/",
        json={"batch_id": batch.id, "movement_type": "in", "quantity": 30,
              "reverses_id": out_id, "reference": "Reversal"},
        headers=auth_headers(admin_user),
    )
    assert back.status_code == 201
    assert back.json()["reverses_id"] == out_id
    assert back.json()["current_quantity"] == 100

    resp = await client.get(f"/batches/{batch.id}", headers=auth_headers(admin_user))
    assert resp.json()["quantity"] == 100


@pytest.mark.asyncio
async def test_create_movement_batch_not_found(client, admin_user, auth_headers):
    resp = await client.post(
        "/stock-movements/",
        json={"batch_id": 999999, "movement_type": "in", "quantity": 5},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_movement_forbidden_for_seller(
    client, seller_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    resp = await client.post(
        "/stock-movements/",
        json={"batch_id": batch.id, "movement_type": "in", "quantity": 5},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_movement_unauthenticated(
    client, create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch,
):
    batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    resp = await client.post(
        "/stock-movements/",
        json={"batch_id": batch.id, "movement_type": "in", "quantity": 5},
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# GET /stock-movements/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_stock_movements_authenticated(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    await client.post(
        "/stock-movements/",
        json={"batch_id": batch.id, "movement_type": "in", "quantity": 10},
        headers=auth_headers(admin_user),
    )
    await client.post(
        "/stock-movements/",
        json={"batch_id": batch.id, "movement_type": "out", "quantity": 5},
        headers=auth_headers(admin_user),
    )
    resp = await client.get("/stock-movements/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3  # origin IN + 2 created
    assert data["limit"] == 20
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_list_stock_movements_filter_by_batch(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    batch_a = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    batch_b = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=50,
    )
    resp = await client.get(
        "/stock-movements/", params={"batch_id": batch_a.id},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1  # only batch_a's origin IN
    assert all(m["batch_id"] == batch_a.id for m in data["items"])


@pytest.mark.asyncio
async def test_list_stock_movements_unauthenticated(client):
    resp = await client.get("/stock-movements/")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# GET /stock-movements/{id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_stock_movement(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch, create_stock_movement,
):
    batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, quantity=100,
    )
    movement = await create_stock_movement(
        batch.id, MovementType.OUT, quantity=20, prev_quantity=100, current_quantity=80,
    )
    resp = await client.get(
        f"/stock-movements/{movement.id}", headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == movement.id
    assert data["movement_type"] == "out"
    assert data["prev_quantity"] == 100
    assert data["current_quantity"] == 80


@pytest.mark.asyncio
async def test_get_stock_movement_not_found(client, admin_user, auth_headers):
    resp = await client.get("/stock-movements/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Immutability: no update / delete routes exposed
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_stock_movement_not_allowed(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch, create_stock_movement,
):
    batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    movement = await create_stock_movement(batch.id, MovementType.IN, quantity=5)
    resp = await client.put(
        f"/stock-movements/{movement.id}", json={"quantity": 10},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_delete_stock_movement_not_allowed(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch, create_stock_movement,
):
    batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    movement = await create_stock_movement(batch.id, MovementType.IN, quantity=5)
    resp = await client.delete(
        f"/stock-movements/{movement.id}", headers=auth_headers(admin_user)
    )
    assert resp.status_code == 405
