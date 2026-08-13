import pytest


_seq = 0


def _next():
    global _seq
    _seq += 1
    return _seq


@pytest.mark.asyncio
async def test_create_sell_deducts_batch_and_creates_receivable(
    client, db_session, admin_user, auth_headers,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    n = _next()
    company = await create_company("Company")
    category = await create_category("Category")
    variant = await create_product_variant("Variant")
    product = await create_product("Prod", company.id, category.id, variant.id)
    supplier = await create_supplier("Sup", phone=f"01127{n:05d}")
    batch = await create_batch(product.id, supplier.id, received_quantity=10, units_per_package=1)
    customer = await create_customer("Cust", phone=f"0134{n:05d}")

    resp = await client.post(
        "/sells/",
        json={
            "customer_id": customer.id,
            "sell_date": "2026-08-13",
            "items": [{"batch_id": batch.id, "quantity": 3, "unit_price": 150.0}],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["sell_number"].startswith("SALE-")
    assert data["items"][0]["quantity"] == 3

    await db_session.refresh(batch)
    assert batch.quantity == 7

    bal = await client.get(
        "/customer-payments/balance",
        params={"customer_id": customer.id},
        headers=auth_headers(admin_user),
    )
    assert bal.status_code == 200
    b = bal.json()
    assert b["total_sold"] == 450.0
    assert b["balance"] == 450.0
    assert any(row["batch_id"] == batch.id and row["outstanding"] == 450.0 for row in b["batches"])


@pytest.mark.asyncio
async def test_over_sell_rejected(
    client, admin_user, auth_headers,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    n = _next()
    company = await create_company("Company")
    category = await create_category("Category")
    variant = await create_product_variant("Variant")
    product = await create_product("Prod", company.id, category.id, variant.id)
    supplier = await create_supplier("Sup", phone=f"01128{n:05d}")
    batch = await create_batch(product.id, supplier.id, received_quantity=10, units_per_package=1)
    customer = await create_customer("Cust", phone=f"0135{n:05d}")

    resp = await client.post(
        "/sells/",
        json={
            "customer_id": customer.id,
            "sell_date": "2026-08-13",
            "items": [{"batch_id": batch.id, "quantity": 20, "unit_price": 150.0}],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_sell_forbidden_for_seller(
    client, seller_user, auth_headers,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    n = _next()
    company = await create_company("Company")
    category = await create_category("Category")
    variant = await create_product_variant("Variant")
    product = await create_product("Prod", company.id, category.id, variant.id)
    supplier = await create_supplier("Sup", phone=f"01129{n:05d}")
    batch = await create_batch(product.id, supplier.id, received_quantity=10, units_per_package=1)
    customer = await create_customer("Cust", phone=f"0136{n:05d}")

    resp = await client.post(
        "/sells/",
        json={
            "customer_id": customer.id,
            "sell_date": "2026-08-13",
            "items": [{"batch_id": batch.id, "quantity": 1, "unit_price": 150.0}],
        },
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_sell_unauthenticated(
    client, create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    n = _next()
    company = await create_company("Company")
    category = await create_category("Category")
    variant = await create_product_variant("Variant")
    product = await create_product("Prod", company.id, category.id, variant.id)
    supplier = await create_supplier("Sup", phone=f"01130{n:05d}")
    batch = await create_batch(product.id, supplier.id, received_quantity=10, units_per_package=1)
    customer = await create_customer("Cust", phone=f"0137{n:05d}")

    resp = await client.post(
        "/sells/",
        json={
            "customer_id": customer.id,
            "sell_date": "2026-08-13",
            "items": [{"batch_id": batch.id, "quantity": 1, "unit_price": 150.0}],
        },
    )
    assert resp.status_code == 401
