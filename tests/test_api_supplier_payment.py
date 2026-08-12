"""
Integration tests for the supplier-payment / payable ledger.

Payments are immutable append-only entries; the payable balance is derived as
    total_cost - returned_value - paid.
Overpayments are rejected, and supplier returns reduce what is owed.
"""
import pytest


async def _make_batch(
    create_company,
    create_category,
    create_product_variant,
    create_product,
    create_supplier,
    create_batch,
    qty=200,
    unit_price=10.0,
):
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)
    supplier = await create_supplier("Acme Supplies", phone="01124111111")
    batch = await create_batch(
        product.id, supplier.id,
        received_quantity=qty, units_per_package=1, unit_price=unit_price,
    )
    return supplier, batch


def _payload(supplier, batch, amount, **overrides):
    data = {
        "supplier_id": supplier.id,
        "batch_id": batch.id,
        "amount": amount,
        "payment_date": "2026-08-12",
        "payment_method": "bank",
    }
    data.update(overrides)
    return data


# --------------------------------------------------------------------------- #
# POST /supplier-payments/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_partial_payments_track_outstanding(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, qty=200, unit_price=10.0,
    )  # total_cost = 2000

    r = await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 1800),
        headers=auth_headers(admin_user),
    )
    assert r.status_code == 201
    assert r.json()["amount"] == 1800

    summary = await client.get(
        "/supplier-payments/summary", params={"batch_id": batch.id},
        headers=auth_headers(admin_user),
    )
    assert summary.status_code == 200
    assert summary.json()["total_cost"] == 2000
    assert summary.json()["paid"] == 1800
    assert summary.json()["returned_value"] == 0
    assert summary.json()["outstanding"] == 200

    # Second payment clears the balance
    r = await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 200),
        headers=auth_headers(admin_user),
    )
    assert r.status_code == 201

    summary = await client.get(
        "/supplier-payments/summary", params={"batch_id": batch.id},
        headers=auth_headers(admin_user),
    )
    assert summary.json()["paid"] == 2000
    assert summary.json()["outstanding"] == 0


@pytest.mark.asyncio
async def test_overpayment_rejected(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, qty=200, unit_price=10.0,
    )
    await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 1800),
        headers=auth_headers(admin_user),
    )
    # Only 200 remains outstanding; pay 500 -> reject
    r = await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 500),
        headers=auth_headers(admin_user),
    )
    assert r.status_code == 400

    summary = await client.get(
        "/supplier-payments/summary", params={"batch_id": batch.id},
        headers=auth_headers(admin_user),
    )
    assert summary.json()["paid"] == 1800
    assert summary.json()["outstanding"] == 200


@pytest.mark.asyncio
async def test_supplier_return_reduces_payable_creating_credit(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, qty=200, unit_price=10.0,
    )  # total = 2000
    # Pay in full
    await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 2000),
        headers=auth_headers(admin_user),
    )
    summary = await client.get(
        "/supplier-payments/summary", params={"batch_id": batch.id},
        headers=auth_headers(admin_user),
    )
    assert summary.json()["outstanding"] == 0

    # Return 20 units @ 10 = 200 -> reduces what we owe -> credit of -200
    r = await client.post(
        "/supplier-returns/",
        json={
            "supplier_id": supplier.id,
            "return_date": "2026-08-12",
            "items": [{"batch_id": batch.id, "quantity": 20, "unit_price": 10.0}],
        },
        headers=auth_headers(admin_user),
    )
    assert r.status_code == 201

    summary = await client.get(
        "/supplier-payments/summary", params={"batch_id": batch.id},
        headers=auth_headers(admin_user),
    )
    assert summary.json()["returned_value"] == 200
    assert summary.json()["outstanding"] == -200  # supplier credit

    # No more payments allowed while in credit
    r = await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 100),
        headers=auth_headers(admin_user),
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_payment_wrong_supplier_rejected(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    other = await create_supplier("Other", phone="01124222222")
    r = await client.post(
        "/supplier-payments/", json=_payload(other, batch, 100),
        headers=auth_headers(admin_user),
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_payment_supplier_not_found(client, admin_user, auth_headers):
    r = await client.post(
        "/supplier-payments/",
        json={
            "supplier_id": 999999, "batch_id": 1, "amount": 100,
            "payment_date": "2026-08-12",
        },
        headers=auth_headers(admin_user),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_payment_batch_not_found(
    client, admin_user, auth_headers, create_supplier,
):
    supplier = await create_supplier("Sup", phone="01124333333")
    r = await client.post(
        "/supplier-payments/",
        json={
            "supplier_id": supplier.id, "batch_id": 999999, "amount": 100,
            "payment_date": "2026-08-12",
        },
        headers=auth_headers(admin_user),
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_payment_forbidden_for_seller(
    client, seller_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    r = await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 100),
        headers=auth_headers(seller_user),
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_payment_unauthenticated(
    client, create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    r = await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 100),
    )
    assert r.status_code == 401


# --------------------------------------------------------------------------- #
# GET /supplier-payments/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_supplier_payments_authenticated(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, qty=200, unit_price=10.0,
    )
    await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 1000),
        headers=auth_headers(admin_user),
    )
    await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 500),
        headers=auth_headers(admin_user),
    )
    resp = await client.get("/supplier-payments/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["items"][0]["supplier"]["id"] == supplier.id
    assert data["items"][0]["batch"]["id"] == batch.id


@pytest.mark.asyncio
async def test_list_supplier_payments_filter_by_batch(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, qty=200, unit_price=10.0,
    )
    await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 1000),
        headers=auth_headers(admin_user),
    )
    resp = await client.get(
        "/supplier-payments/", params={"batch_id": batch.id},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_supplier_payments_unauthenticated(client):
    resp = await client.get("/supplier-payments/")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# GET /supplier-payments/{id} & /summary
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_supplier_payment(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, qty=200, unit_price=10.0,
    )
    created = await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 500),
        headers=auth_headers(admin_user),
    )
    payment_id = created.json()["id"]
    resp = await client.get(
        f"/supplier-payments/{payment_id}", headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == payment_id
    assert resp.json()["amount"] == 500


@pytest.mark.asyncio
async def test_get_supplier_payment_not_found(client, admin_user, auth_headers):
    resp = await client.get("/supplier-payments/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_summary_batch_not_found(client, admin_user, auth_headers):
    resp = await client.get(
        "/supplier-payments/summary", params={"batch_id": 999999},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Immutability: no update / delete routes exposed
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_supplier_payment_not_allowed(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, qty=200, unit_price=10.0,
    )
    created = await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 500),
        headers=auth_headers(admin_user),
    )
    payment_id = created.json()["id"]
    resp = await client.put(
        f"/supplier-payments/{payment_id}", json={"amount": 10},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 405


@pytest.mark.asyncio
async def test_delete_supplier_payment_not_allowed(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    supplier, batch = await _make_batch(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, qty=200, unit_price=10.0,
    )
    created = await client.post(
        "/supplier-payments/", json=_payload(supplier, batch, 500),
        headers=auth_headers(admin_user),
    )
    payment_id = created.json()["id"]
    resp = await client.delete(
        f"/supplier-payments/{payment_id}", headers=auth_headers(admin_user)
    )
    assert resp.status_code == 405
