import pytest


_seq = 0


def _next():
    global _seq
    _seq += 1
    return _seq


async def _sold_batch(client, admin_user, auth_headers, db_session,
                     create_company, create_category, create_product_variant,
                     create_product, create_supplier, create_batch, create_customer):
    n = _next()
    company = await create_company("Company")
    category = await create_category("Category")
    variant = await create_product_variant("Variant")
    product = await create_product("Prod", company.id, category.id, variant.id)
    supplier = await create_supplier("Sup", phone=f"01131{n:05d}")
    batch = await create_batch(product.id, supplier.id, received_quantity=10, units_per_package=1)
    customer = await create_customer("Cust", phone=f"0138{n:05d}")

    sell = await client.post(
        "/sells/",
        json={
            "customer_id": customer.id,
            "sell_date": "2026-08-13",
            "items": [{"batch_id": batch.id, "quantity": 3, "unit_price": 150.0}],
        },
        headers=auth_headers(admin_user),
    )
    assert sell.status_code == 201
    return batch, customer


@pytest.mark.asyncio
async def test_create_return_restocks_batch_and_reduces_receivable(
    client, admin_user, auth_headers, db_session,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    batch, customer = await _sold_batch(
        client, admin_user, auth_headers, db_session,
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, create_customer,
    )

    resp = await client.post(
        "/customer-returns/",
        json={
            "customer_id": customer.id,
            "return_date": "2026-08-14",
            "reason": "Damaged",
            "items": [{"batch_id": batch.id, "quantity": 1, "unit_price": 150.0}],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["return_number"].startswith("CR-")

    await db_session.refresh(batch)
    assert batch.quantity == 8

    bal = await client.get(
        "/customer-payments/balance",
        params={"customer_id": customer.id},
        headers=auth_headers(admin_user),
    )
    assert bal.status_code == 200
    b = bal.json()
    assert b["total_sold"] == 450.0
    assert b["total_returned"] == 150.0
    assert b["balance"] == 300.0


@pytest.mark.asyncio
async def test_return_batch_not_found_forbidden_and_unauth(
    client, admin_user, seller_user, auth_headers,
    create_company, create_category, create_product_variant,
    create_product, create_supplier, create_batch, create_customer,
):
    batch, customer = await _sold_batch(
        client, admin_user, auth_headers, None,
        create_company, create_category, create_product_variant,
        create_product, create_supplier, create_batch, create_customer,
    )

    # 404 for an unknown batch
    resp = await client.post(
        "/customer-returns/",
        json={
            "customer_id": customer.id,
            "return_date": "2026-08-14",
            "items": [{"batch_id": 999999, "quantity": 1, "unit_price": 150.0}],
        },
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 404

    # 403 for a seller
    resp = await client.post(
        "/customer-returns/",
        json={
            "customer_id": customer.id,
            "return_date": "2026-08-14",
            "items": [{"batch_id": batch.id, "quantity": 1, "unit_price": 150.0}],
        },
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403

    # 401 unauthenticated
    resp = await client.post(
        "/customer-returns/",
        json={
            "customer_id": customer.id,
            "return_date": "2026-08-14",
            "items": [{"batch_id": batch.id, "quantity": 1, "unit_price": 150.0}],
        },
    )
    assert resp.status_code == 401
