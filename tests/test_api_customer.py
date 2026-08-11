"""
Integration tests for the /customers endpoints including role-based authorization.
"""
import pytest
from sqlalchemy import select

from app.models.customer import Customer


def _customer_payload(**overrides):
    payload = {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "01123456789",
        "nid": "1234567890",
        "customer_type": "walk_in",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# GET /customers/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_customers_authenticated(client, admin_user, auth_headers, create_customer):
    await create_customer("John Doe")
    await create_customer("Jane Roe", phone="01123456788")
    resp = await client.get("/customers/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["skip"] == 0
    assert data["limit"] == 20
    assert [c["name"] for c in data["items"]] == ["John Doe", "Jane Roe"]


@pytest.mark.asyncio
async def test_list_customers_allows_seller(client, seller_user, auth_headers, create_customer):
    await create_customer("Sam Seller")
    resp = await client.get("/customers/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert [c["name"] for c in resp.json()["items"]] == ["Sam Seller"]


@pytest.mark.asyncio
async def test_list_customers_pagination(client, admin_user, auth_headers, create_customer):
    for i in range(3):
        await create_customer(f"Customer {i}", phone=f"0112000000{i}")

    resp = await client.get(
        "/customers/", params={"skip": 0, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert len(data["items"]) == 2

    resp = await client.get(
        "/customers/", params={"skip": 2, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_customers_empty_database(client, seller_user, auth_headers):
    resp = await client.get("/customers/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_customers_unauthenticated(client):
    resp = await client.get("/customers/")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# POST /customers/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_customer_by_admin(client, admin_user, auth_headers):
    resp = await client.post(
        "/customers/", json=_customer_payload(), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "John Doe"
    assert data["phone"] == "01123456789"
    assert data["customer_type"] == "walk_in"
    assert data["id"] is not None
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_create_customer_registered_type(client, admin_user, auth_headers):
    resp = await client.post(
        "/customers/",
        json=_customer_payload(customer_type="registered"),
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 201
    assert resp.json()["customer_type"] == "registered"


@pytest.mark.asyncio
async def test_create_customer_by_superadmin(client, super_admin_user, auth_headers):
    resp = await client.post(
        "/customers/", json=_customer_payload(name="Boss"), headers=auth_headers(super_admin_user)
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Boss"


@pytest.mark.asyncio
async def test_create_customer_forbidden_for_seller(client, seller_user, auth_headers):
    resp = await client.post(
        "/customers/", json=_customer_payload(), headers=auth_headers(seller_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_customer_forbidden_for_store_keeper(client, store_keeper_user, auth_headers):
    resp = await client.post(
        "/customers/", json=_customer_payload(), headers=auth_headers(store_keeper_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_customer_unauthenticated(client):
    resp = await client.post("/customers/", json=_customer_payload())
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_customer_empty_name_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/customers/", json=_customer_payload(name=""), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_customer_invalid_type_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/customers/", json=_customer_payload(customer_type="vip"), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_customer_short_phone_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/customers/", json=_customer_payload(phone="123"), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_customer_invalid_email_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/customers/", json=_customer_payload(email="not-an-email"), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_customer_long_phone_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/customers/", json=_customer_payload(phone="0" * 21), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# GET /customers/{customer_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_customer_by_id(client, admin_user, auth_headers, create_customer):
    customer = await create_customer("John Doe")
    resp = await client.get(f"/customers/{customer.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == customer.id
    assert data["name"] == "John Doe"
    assert data["phone"] == "01123456789"


@pytest.mark.asyncio
async def test_get_customer_by_id_allows_seller(client, seller_user, auth_headers, create_customer):
    customer = await create_customer("Sam Seller")
    resp = await client.get(f"/customers/{customer.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Sam Seller"


@pytest.mark.asyncio
async def test_get_customer_not_found(client, admin_user, auth_headers):
    resp = await client.get("/customers/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_customer_unauthenticated(client, create_customer):
    customer = await create_customer("John Doe")
    resp = await client.get(f"/customers/{customer.id}")
    assert resp.status_code == 401
@pytest.mark.asyncio
async def test_update_customer_by_admin(client, db_session, admin_user, auth_headers, create_customer):
    customer = await create_customer("Old Name")
    resp = await client.put(
        f"/customers/{customer.id}",
        json={"name": "New Name"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == customer.id
    assert data["name"] == "New Name"

    # Verify the existing row was updated in place (no duplicate row created).
    result = await db_session.execute(select(Customer).where(Customer.id == customer.id))
    updated = result.scalar_one()
    await db_session.refresh(updated)
    assert updated.name == "New Name"


@pytest.mark.asyncio
async def test_update_customer_not_found(client, admin_user, auth_headers):
    resp = await client.put(
        "/customers/999999", json={"name": "Nope"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_customer_forbidden_for_seller(client, seller_user, auth_headers, create_customer):
    customer = await create_customer("Initech")
    resp = await client.put(
        f"/customers/{customer.id}",
        json={"name": "Hacked"},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_customer_unauthenticated(client, create_customer):
    customer = await create_customer("Initech")
    resp = await client.put(f"/customers/{customer.id}", json={"name": "New"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_customer_empty_name_rejected(client, admin_user, auth_headers, create_customer):
    customer = await create_customer("John Doe")
    resp = await client.put(
        f"/customers/{customer.id}",
        json={"name": ""},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# DELETE /customers/{customer_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_delete_customer_by_admin(client, admin_user, auth_headers, create_customer):
    customer = await create_customer("John Doe")
    resp = await client.delete(f"/customers/{customer.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["message"] == "Customer deleted successfully"

    resp = await client.get(f"/customers/{customer.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_customer_not_found(client, admin_user, auth_headers):
    resp = await client.delete("/customers/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_customer_forbidden_for_seller(client, seller_user, auth_headers, create_customer):
    customer = await create_customer("Initech")
    resp = await client.delete(f"/customers/{customer.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_customer_unauthenticated(client, create_customer):
    customer = await create_customer("Initech")
    resp = await client.delete(f"/customers/{customer.id}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Pagination / query validation
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_customers_invalid_limit_rejected(client, admin_user, auth_headers):
    resp = await client.get(
        "/customers/", params={"limit": 0}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422
