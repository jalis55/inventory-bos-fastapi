"""
Integration tests for the /companies endpoints including role-based authorization.
"""
import pytest
from sqlalchemy import select

from app.models.company import Company


# --------------------------------------------------------------------------- #
# GET /companies/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_companies_authenticated(client, admin_user, auth_headers, create_company):
    await create_company("Acme Corp")
    await create_company("Globex")
    resp = await client.get("/companies/", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["skip"] == 0
    assert data["limit"] == 20
    assert [c["name"] for c in data["items"]] == ["Acme Corp", "Globex"]


@pytest.mark.asyncio
async def test_list_companies_allows_seller(client, seller_user, auth_headers, create_company):
    await create_company("Initech")
    resp = await client.get("/companies/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert [c["name"] for c in resp.json()["items"]] == ["Initech"]


@pytest.mark.asyncio
async def test_list_companies_pagination(client, admin_user, auth_headers, create_company):
    for i in range(3):
        await create_company(f"Company {i}")

    resp = await client.get(
        "/companies/", params={"skip": 0, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["limit"] == 2
    assert len(data["items"]) == 2

    resp = await client.get(
        "/companies/", params={"skip": 2, "limit": 2}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_companies_unauthenticated(client):
    resp = await client.get("/companies/")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# POST /companies/
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_company_by_admin(client, admin_user, auth_headers):
    resp = await client.post(
        "/companies/", json={"name": "Acme Corp"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Acme Corp"
    assert data["id"] is not None
    assert data["created_at"] is not None


@pytest.mark.asyncio
async def test_create_company_by_superadmin(client, super_admin_user, auth_headers):
    resp = await client.post(
        "/companies/", json={"name": "Stark Industries"}, headers=auth_headers(super_admin_user)
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Stark Industries"


@pytest.mark.asyncio
async def test_create_company_forbidden_for_seller(client, seller_user, auth_headers):
    resp = await client.post(
        "/companies/", json={"name": "Umbrella Corp"}, headers=auth_headers(seller_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_company_forbidden_for_store_keeper(client, store_keeper_user, auth_headers):
    resp = await client.post(
        "/companies/", json={"name": "Umbrella Corp"}, headers=auth_headers(store_keeper_user)
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_company_unauthenticated(client):
    resp = await client.post("/companies/", json={"name": "Acme Corp"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_company_empty_name_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/companies/", json={"name": ""}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_company_name_too_long_rejected(client, admin_user, auth_headers):
    resp = await client.post(
        "/companies/", json={"name": "x" * 51}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# GET /companies/{company_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_company_by_id(client, admin_user, auth_headers, create_company):
    company = await create_company("Acme Corp")
    resp = await client.get(f"/companies/{company.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == company.id
    assert data["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_get_company_by_id_allows_seller(client, seller_user, auth_headers, create_company):
    company = await create_company("Initech")
    resp = await client.get(f"/companies/{company.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    assert resp.json()["name"] == "Initech"


@pytest.mark.asyncio
async def test_get_company_not_found(client, admin_user, auth_headers):
    resp = await client.get("/companies/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_company_unauthenticated(client, create_company):
    company = await create_company("Acme Corp")
    resp = await client.get(f"/companies/{company.id}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# PUT /companies/{company_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_update_company_by_admin(client, db_session, admin_user, auth_headers, create_company):
    company = await create_company("Old Name")
    resp = await client.put(
        f"/companies/{company.id}",
        json={"name": "New Name"},
        headers=auth_headers(admin_user),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == company.id
    assert data["name"] == "New Name"

    # Verify the existing row was updated in place (no duplicate row created).
    result = await db_session.execute(
        select(Company).where(Company.id == company.id)
    )
    updated = result.scalar_one()
    await db_session.refresh(updated)
    assert updated.name == "New Name"


@pytest.mark.asyncio
async def test_update_company_not_found(client, admin_user, auth_headers):
    resp = await client.put(
        "/companies/999999", json={"name": "Nope"}, headers=auth_headers(admin_user)
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_company_forbidden_for_seller(client, seller_user, auth_headers, create_company):
    company = await create_company("Initech")
    resp = await client.put(
        f"/companies/{company.id}",
        json={"name": "Hacked"},
        headers=auth_headers(seller_user),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_update_company_unauthenticated(client, create_company):
    company = await create_company("Initech")
    resp = await client.put(f"/companies/{company.id}", json={"name": "New"})
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# DELETE /companies/{company_id}
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_delete_company_by_admin(client, admin_user, auth_headers, create_company):
    company = await create_company("Acme Corp")
    resp = await client.delete(f"/companies/{company.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 200
    assert resp.json()["message"] == "Company deleted successfully"

    resp = await client.get(f"/companies/{company.id}", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_company_not_found(client, admin_user, auth_headers):
    resp = await client.delete("/companies/999999", headers=auth_headers(admin_user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_company_forbidden_for_seller(client, seller_user, auth_headers, create_company):
    company = await create_company("Initech")
    resp = await client.delete(f"/companies/{company.id}", headers=auth_headers(seller_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_delete_company_unauthenticated(client, create_company):
    company = await create_company("Initech")
    resp = await client.delete(f"/companies/{company.id}")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# Misc
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_companies_empty_database(client, seller_user, auth_headers):
    resp = await client.get("/companies/", headers=auth_headers(seller_user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []