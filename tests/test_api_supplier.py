"""
Integration tests for the /suppliers endpoints including role-based authorization.
"""
import pytest
from sqlalchemy import select

from app.models.supplier import Supplier


def _supplier_payload(**overrides):
    payload = {
        "name": "Acme Supplies",
        "email": "sales@acme.com",
        "phone": "01123456789",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------- #
# GET /suppliers/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_suppliers_authenticated(client, admin_user, auth_headers, create_supplier):
    await create_supplier("Acme Supplies")
    await create_supplier("Globex", phone="01123456788")
    resp = await client.get("/suppliers/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["skip"] == 0
    assert data["limit"] == 20
    assert [s["name"] for s in data["items"]] == ["Acme Supplies", "Globex"]


@pytest.mark.asyncio
async def test_list_suppliers_allows_seller(client, seller_user, auth_headers, create_supplier):
    await create_supplier("Initech")
    resp = await client.get("/suppliers/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert [s["name"] for s in resp.json()["items"]] == ["Initech"]


@pytest.mark.asyncio
async def test_list_suppliers_pagination(client, admin_user, auth_headers, create_supplier):
    for i in range(3):
        await create_supplier(f"Supplier {i}", phone=f"0112000000{i}")

    resp = await client.get(
        "/suppliers/", params={"skip": 0, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert len(data["items"]) == 2

    resp = await client.get(
        "/suppliers/", params={"skip": 2, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_suppliers_empty_database(client, seller_user, auth_headers):
    resp = await client.get("/suppliers/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_suppliers_unauthenticated(client):
    resp = await client.get("/suppliers/")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_suppliers_invalid_limit_rejected(client, admin_user, auth_headers):
    resp = await client.get(
        "/suppliers/", params={"limit": 0}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# POST /suppliers/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_supplier_by_admin(client, admin_user, auth_headers):
    resp = await client.post(
        "/suppliers/", json=_supplier_payload(), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Acme Supplies"
    assert data["phone"] == "01123456789"
    assert data["id"] is not None
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_create_supplier_by_superadmin(client, super_admin_user, auth_headers):
    resp = await client.post(
        "/suppliers/", json=_supplier_payload(name="Hooli"), headers=auth_headers(super_admin_user)
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Hooli"


@pytest.mark.asyncio
async def test_create_supplier_forbidden_for_seller(client, seller_user, auth_headers):
    resp = await client.post(
        "/suppliers/", json=_supplier_payload(), headers=auth_headers(seller_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_supplier_forbidden_for_store_keeper(client, store_keeper_user, auth_headers):
    resp = await client.post(
        "/suppliers/", json=_supplier_payload(), headers=auth_headers(store_keeper_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_supplier_unauthenticated(client):
    resp = await client.post("/suppliers/", json=_supplier_payload())
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_supplier_empty_name_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/suppliers/", json=_supplier_payload(name=""), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_supplier_short_phone_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/suppliers/", json=_supplier_payload(phone="123"), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_supplier_invalid_email_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/suppliers/", json=_supplier_payload(email="not-an-email"), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_supplier_long_phone_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/suppliers/", json=_supplier_payload(phone="0" * 21), headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# GET /suppliers/{supplier_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_supplier_by_id(client, admin_user, auth_headers, create_supplier):
    supplier = await create_supplier("Acme Supplies")
    resp = await client.get(f"/suppliers/{supplier.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == supplier.id
    assert data["name"] == "Acme Supplies"


@pytest.mark.asyncio
async def test_get_supplier_by_id_allows_seller(client, seller_user, auth_headers, create_supplier):
    supplier = await create_supplier("Initech")
    resp = await client.get(f"/suppliers/{supplier.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Initech"


@pytest.mark.asyncio
async def test_get_supplier_not_found(client, admin_user, auth_headers):
    resp = await client.get("/suppliers/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_supplier_unauthenticated(client, create_supplier):
    supplier = await create_supplier("Acme Supplies")
    resp = await client.get(f"/suppliers/{supplier.id}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# PUT /suppliers/{supplier_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_supplier_by_admin(client, db_session, admin_user, auth_headers, create_supplier):
    supplier = await create_supplier("Old Name")
    resp = await client.put(
        f"/suppliers/{supplier.id}",
        json={"name": "New Name"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == supplier.id
    assert data["name"] == "New Name"

    # Verify the existing row was updated in place (no duplicate row created).
    result = await db_session.execute(select(Supplier).where(Supplier.id == supplier.id))
    updated = result.scalar_one()
    await db_session.refresh(updated)
    assert updated.name == "New Name"


@pytest.mark.asyncio
async def test_update_supplier_not_found(client, admin_user, auth_headers):
    resp = await client.put(
        "/suppliers/999999", json={"name": "Nope"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_supplier_forbidden_for_seller(client, seller_user, auth_headers, create_supplier):
    supplier = await create_supplier("Initech")
    resp = await client.put(
        f"/suppliers/{supplier.id}",
        json={"name": "Hacked"},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_supplier_unauthenticated(client, create_supplier):
    supplier = await create_supplier("Initech")
    resp = await client.put(f"/suppliers/{supplier.id}", json={"name": "New"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_supplier_empty_name_rejected(client, admin_user, auth_headers, create_supplier):
    supplier = await create_supplier("Acme Supplies")
    resp = await client.put(
        f"/suppliers/{supplier.id}",
        json={"name": ""},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_supplier_short_phone_rejected(client, admin_user, auth_headers, create_supplier):
    supplier = await create_supplier("Acme Supplies")
    resp = await client.put(
        f"/suppliers/{supplier.id}",
        json={"phone": "123"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# DELETE /suppliers/{supplier_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_delete_supplier_by_admin(client, admin_user, auth_headers, create_supplier):
    supplier = await create_supplier("Acme Supplies")
    resp = await client.delete(f"/suppliers/{supplier.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["message"] == "Supplier deleted successfully"

    resp = await client.get(f"/suppliers/{supplier.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_supplier_not_found(client, admin_user, auth_headers):
    resp = await client.delete("/suppliers/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_supplier_forbidden_for_seller(client, seller_user, auth_headers, create_supplier):
    supplier = await create_supplier("Initech")
    resp = await client.delete(f"/suppliers/{supplier.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_supplier_unauthenticated(client, create_supplier):
    supplier = await create_supplier("Initech")
    resp = await client.delete(f"/suppliers/{supplier.id}")
    assert resp.status_code == 401

