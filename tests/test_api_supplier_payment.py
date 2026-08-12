"""
Integration tests for the supplier-payment / supplier account ledger.

Transactions are immutable append-only entries with a ``payment_type``
(``payment`` or ``collection``) and an optional batch link. The supplier-level
balance is derived:

    balance = total_received - total_returned - total_paid + total_collected

Payments and collections validate against the supplier-level balance, so a
return-created credit on one batch can offset dues on another batch of the same
supplier (a negative balance means the supplier owes us).
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


# --------------------------------------------------------------------------- #
# Supplier-level balance (payment_type: payment / collection)
# --------------------------------------------------------------------------- #
async def _make_credit_supplier(
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch,
):
    """Creates a supplier with three batches: 10@10=100, 20@4=80, 5@50=250."""
    company = await create_company("Acme Corp")
    category = await create_category("Electronics")
    variant = await create_product_variant("Small")
    product = await create_product("Laptop", company.id, category.id, variant.id)
    supplier = await create_supplier("Acme Supplies", phone="01125000001")
    b1 = await create_batch(product.id, supplier.id,
                            received_quantity=10, units_per_package=1, unit_price=10.0)
    b2 = await create_batch(product.id, supplier.id,
                            received_quantity=20, units_per_package=1, unit_price=4.0)
    b3 = await create_batch(product.id, supplier.id,
                            received_quantity=5, units_per_package=1, unit_price=50.0)
    return supplier, b1, b2, b3


async def _pay_off_and_return(
    client, headers, supplier, b1, b2, b3,
):
    """Pay b1 fully, b2 partially (40), b3 fully; then return 10 from b2 (40)
    and 2 from b3 (100) -> supplier balance -100 (supplier owes us)."""
    for batch, amount in [(b1, 100), (b2, 40), (b3, 250)]:
        r = await client.post(
            "/supplier-payments/", json=_payload(supplier, batch, amount),
            headers=headers,
        )
        assert r.status_code == 201
    r = await client.post("/supplier-returns/", json={
        "supplier_id": supplier.id, "return_date": "2026-08-12",
        "items": [{"batch_id": b2.id, "quantity": 10, "unit_price": 4.0}],
    }, headers=headers)
    assert r.status_code == 201
    r = await client.post("/supplier-returns/", json={
        "supplier_id": supplier.id, "return_date": "2026-08-12",
        "items": [{"batch_id": b3.id, "quantity": 2, "unit_price": 50.0}],
    }, headers=headers)
    assert r.status_code == 201


async def balance_json(client, headers, supplier):
    resp = await client.get(
        "/supplier-payments/balance", params={"supplier_id": supplier.id},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


async def bal_of(client, headers, supplier):
    return (await balance_json(client, headers, supplier))["balance"]


@pytest.mark.asyncio
async def test_supplier_level_balance_nets_across_batches(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    headers = auth_headers(admin_user)
    supplier, b1, b2, b3 = await _make_credit_supplier(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )

    bal = await client.get(
        "/supplier-payments/balance", params={"supplier_id": supplier.id},
        headers=headers,
    )
    assert bal.status_code == 200
    data = bal.json()
    assert data["total_received"] == 430
    assert data["balance"] == 430

    # Pay batch-1 fully, batch-2 partially (40), batch-3 fully -> balance 40
    for batch, amount in [(b1, 100), (b2, 40), (b3, 250)]:
        r = await client.post(
            "/supplier-payments/", json=_payload(supplier, batch, amount),
            headers=headers,
        )
        assert r.status_code == 201

    bal = await client.get(
        "/supplier-payments/balance", params={"supplier_id": supplier.id},
        headers=headers,
    )
    data = bal.json()
    assert data["total_paid"] == 390
    assert data["balance"] == 40

    # Return 10 from batch-2 (40) -> balance 0
    r = await client.post("/supplier-returns/", json={
        "supplier_id": supplier.id, "return_date": "2026-08-12",
        "items": [{"batch_id": b2.id, "quantity": 10, "unit_price": 4.0}],
    }, headers=headers)
    assert r.status_code == 201

    bal = await client.get(
        "/supplier-payments/balance", params={"supplier_id": supplier.id},
        headers=headers,
    )
    data = bal.json()
    assert data["total_returned"] == 40
    assert data["balance"] == 0

    # Return 2 from batch-3 (100) -> supplier owes us 100
    r = await client.post("/supplier-returns/", json={
        "supplier_id": supplier.id, "return_date": "2026-08-12",
        "items": [{"batch_id": b3.id, "quantity": 2, "unit_price": 50.0}],
    }, headers=headers)
    assert r.status_code == 201

    bal = await client.get(
        "/supplier-payments/balance", params={"supplier_id": supplier.id},
        headers=headers,
    )
    data = bal.json()
    assert data["total_returned"] == 140
    assert data["balance"] == -100  # supplier owes us
    assert len(data["batches"]) == 3


@pytest.mark.asyncio
async def test_collection_settles_supplier_credit(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    headers = auth_headers(admin_user)
    supplier, b1, b2, b3 = await _make_credit_supplier(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    await _pay_off_and_return(client, headers, supplier, b1, b2, b3)
    assert await bal_of(client, headers, supplier) == -100

    r = await client.post("/supplier-payments/", json={
        "supplier_id": supplier.id, "payment_type": "collection",
        "amount": 100, "payment_date": "2026-08-12",
    }, headers=headers)
    assert r.status_code == 201
    assert r.json()["payment_type"] == "collection"

    data = await balance_json(client, headers, supplier)
    assert data["total_collected"] == 100
    assert data["balance"] == 0


@pytest.mark.asyncio
async def test_payment_rejected_when_supplier_owes_us(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    headers = auth_headers(admin_user)
    supplier, b1, b2, b3 = await _make_credit_supplier(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    await _pay_off_and_return(client, headers, supplier, b1, b2, b3)

    r = await client.post(
        "/supplier-payments/", json=_payload(supplier, b1, 50),
        headers=headers,
    )
    assert r.status_code == 400  # balance is -100, cannot pay


@pytest.mark.asyncio
async def test_collection_rejected_when_no_credit(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    headers = auth_headers(admin_user)
    supplier, b1, b2, b3 = await _make_credit_supplier(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    # No payments -> balance is 430 (we owe), so we cannot collect
    r = await client.post("/supplier-payments/", json={
        "supplier_id": supplier.id, "payment_type": "collection",
        "amount": 50, "payment_date": "2026-08-12",
    }, headers=headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_over_collection_rejected(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    headers = auth_headers(admin_user)
    supplier, b1, b2, b3 = await _make_credit_supplier(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    await _pay_off_and_return(client, headers, supplier, b1, b2, b3)  # -100
    r = await client.post("/supplier-payments/", json={
        "supplier_id": supplier.id, "payment_type": "collection",
        "amount": 150, "payment_date": "2026-08-12",
    }, headers=headers)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_supplier_level_payment_without_batch(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    headers = auth_headers(admin_user)
    supplier, b1, *_ = await _make_credit_supplier(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    # batch_id is optional: pay at the supplier level
    r = await client.post("/supplier-payments/", json={
        "supplier_id": supplier.id,
        "amount": 100, "payment_date": "2026-08-12",
    }, headers=headers)
    assert r.status_code == 201
    assert r.json()["batch_id"] is None

    data = await balance_json(client, headers, supplier)
    assert data["total_paid"] == 100


@pytest.mark.asyncio
async def test_payment_type_defaults_to_payment(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    headers = auth_headers(admin_user)
    supplier, b1, *_ = await _make_credit_supplier(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    r = await client.post(
        "/supplier-payments/", json=_payload(supplier, b1, 50),
        headers=headers,
    )
    assert r.status_code == 201
    assert r.json()["payment_type"] == "payment"


@pytest.mark.asyncio
async def test_return_credit_offsets_other_batch_dues(
    client, admin_user, auth_headers, create_company, create_category,
    create_product_variant, create_product, create_supplier, create_batch,
):
    headers = auth_headers(admin_user)
    supplier, b1, b2, b3 = await _make_credit_supplier(
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch,
    )
    # batch-1 (100) unpaid -> dues 100; batch-3 (5@50=250) fully paid.
    r = await client.post(
        "/supplier-payments/", json=_payload(supplier, b3, 250),
        headers=headers,
    )
    assert r.status_code == 201

    # Return 2 from batch-3 @ 50 = 100 -> its credit offsets batch-1's dues.
    r = await client.post("/supplier-returns/", json={
        "supplier_id": supplier.id, "return_date": "2026-08-12",
        "items": [{"batch_id": b3.id, "quantity": 2, "unit_price": 50.0}],
    }, headers=headers)
    assert r.status_code == 201

    data = await balance_json(client, headers, supplier)
    # received 100+80+250=430; paid 250; returned 100 -> balance 80
    assert data["total_received"] == 430
    assert data["total_paid"] == 250
    assert data["total_returned"] == 100
    assert data["balance"] == 80

    # Per-batch: batch-1 outstanding 100, batch-3 outstanding -100
    by_id = {row["batch_id"]: row for row in data["batches"]}
    assert by_id[b1.id]["outstanding"] == 100
    assert by_id[b3.id]["outstanding"] == -100

    # Because the supplier balance is 80, an 80 payment is accepted.
    r = await client.post(
        "/supplier-payments/", json=_payload(supplier, b1, 80),
        headers=headers,
    )
    assert r.status_code == 201
    assert await bal_of(client, headers, supplier) == 0


@pytest.mark.asyncio
async def test_balance_supplier_not_found(client, admin_user, auth_headers):
    resp = await client.get(
        "/supplier-payments/balance", params={"supplier_id": 999999},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 404





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
