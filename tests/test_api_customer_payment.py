import pytest


_seq = 0


def _next():
    global _seq
    _seq += 1
    return _seq


async def _fresh_customer_with_sell(
    client, admin_user, auth_headers,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    n = _next()
    company = await create_company("Company")
    category = await create_category("Category")
    variant = await create_product_variant("Variant")
    product = await create_product("Prod", company.id, category.id, variant.id)
    supplier = await create_supplier("Sup", phone=f"01132{n:05d}")
    batch = await create_batch(product.id, supplier.id, received_quantity=10, units_per_package=1)
    customer = await create_customer("Cust", phone=f"0139{n:05d}")

    resp = await client.post(
        "/sells/",
        json={
            "customer_id": customer.id,
            "sell_date": "2026-08-13",
            "items": [{"batch_id": batch.id, "quantity": 3, "unit_price": 150.0}],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201
    return customer


@pytest.mark.asyncio
async def test_collection_reduces_receivable(
    client, admin_user, auth_headers,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    customer = await _fresh_customer_with_sell(
        client, admin_user, auth_headers,
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, create_customer,
    )

    resp = await client.post(
        "/customer-payments/",
        json={
            "customer_id": customer.id,
            "payment_type": "collection",
            "amount": 200,
            "payment_date": "2026-08-14",
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201, resp.text

    bal = await client.get(
        "/customer-payments/balance",
        params={"customer_id": customer.id},
        headers=auth_headers(admin_user),
    )
    assert bal.status_code == 200
    b = bal.json()
    assert b["total_collected"] == 200.0
    assert b["balance"] == 250.0


@pytest.mark.asyncio
async def test_collection_rejected_when_no_receivable(
    client, admin_user, auth_headers,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    n = _next()
    company = await create_company("Company")
    category = await create_category("Category")
    variant = await create_product_variant("Variant")
    product = await create_product("Prod", company.id, category.id, variant.id)
    supplier = await create_supplier("Sup", phone=f"01133{n:05d}")
    await create_batch(product.id, supplier.id, received_quantity=10, units_per_package=1)
    customer = await create_customer("Cust", phone=f"0140{n:05d}")

    resp = await client.post(
        "/customer-payments/",
        json={
            "customer_id": customer.id,
            "payment_type": "collection",
            "amount": 100,
            "payment_date": "2026-08-14",
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_over_collection_rejected(
    client, admin_user, auth_headers,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    customer = await _fresh_customer_with_sell(
        client, admin_user, auth_headers,
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, create_customer,
    )
    resp = await client.post(
        "/customer-payments/",
        json={
            "customer_id": customer.id,
            "payment_type": "collection",
            "amount": 9999,
            "payment_date": "2026-08-14",
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 400

@pytest.mark.asyncio
async def test_batch_scoped_collection(
    client, admin_user, auth_headers,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    customer = await _fresh_customer_with_sell(
        client, admin_user, auth_headers,
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, create_customer,
    )
    balances = (
        await client.get(
            "/customer-payments/balance",
            params={"customer_id": customer.id},
            headers=auth_headers(admin_user),
        )
    ).json()
    batch_id = balances["batches"][0]["batch_id"]

    resp = await client.post(
        "/customer-payments/",
        json={
            "customer_id": customer.id,
            "batch_id": batch_id,
            "payment_type": "collection",
            "amount": 150,
            "payment_date": "2026-08-14",
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_balance_customer_not_found(client, admin_user, auth_headers):
    resp = await client.get(
        "/customer-payments/balance",
        params={"customer_id": 999999},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_payment_forbidden_for_seller_and_unauth(
    client, admin_user, seller_user, auth_headers,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    customer = await _fresh_customer_with_sell(
        client, admin_user, auth_headers,
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, create_customer,
    )
    payload = {
        "customer_id": customer.id,
        "payment_type": "collection",
        "amount": 100,
        "payment_date": "2026-08-14",
    }
    resp = await client.post("/customer-payments/", json=payload, headers=auth_headers(seller_user))
    assert resp.status_code == 403

    resp = await client.post("/customer-payments/", json=payload)
    assert resp.status_code == 401
