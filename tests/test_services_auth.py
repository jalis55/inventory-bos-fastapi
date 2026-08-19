"""
Service-layer tests for app.services.auth against the async test database.

Note: the imported service function ``create_user`` is aliased to
``create_user_service`` to avoid colliding with the ``create_user`` (DB insert
helper) fixture defined in conftest.py.
"""
import pytest
from fastapi import HTTPException

from app.models.user import Role
from app.schemas.auth import UserCreate
from app.services.auth import (
    authenticate_user,
    create_user as create_user_service,
    get_user_by_email,
)
from tests.conftest import TEST_PASSWORD


# --------------------------------------------------------------------------- #
# get_user_by_email
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_user_by_email_found(db_session, create_user):
    user = await create_user("found@example.com", role=Role.ADMIN)
    result = await get_user_by_email(db_session, "found@example.com")
    assert result is not None
    assert result.id == user.id


@pytest.mark.asyncio
async def test_get_user_by_email_missing(db_session):
    assert await get_user_by_email(db_session, "missing@example.com") is None


# --------------------------------------------------------------------------- #
# create_user
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_create_user_super_admin_creates_admin(db_session, super_admin_user):
    user_in = UserCreate(
        email="newadmin@example.com", password=TEST_PASSWORD,
        full_name="New Admin", role=Role.ADMIN,
    )
    created = await create_user_service(db_session, user_in, super_admin_user)
    assert created.role == Role.ADMIN
    assert created.email == "newadmin@example.com"
    assert created.is_active is True


@pytest.mark.asyncio
async def test_create_user_admin_creates_store_keeper(db_session, admin_user):
    user_in = UserCreate(
        email="keeper@x.com", password=TEST_PASSWORD, role=Role.STORE_KEEPER,
    )
    created = await create_user_service(db_session, user_in, admin_user)
    assert created.role == Role.STORE_KEEPER


@pytest.mark.asyncio
async def test_create_user_duplicate_email(db_session, super_admin_user, create_user):
    await create_user("dup@example.com", role=Role.SELLER)
    user_in = UserCreate(email="dup@example.com", password=TEST_PASSWORD, role=Role.SELLER)
    with pytest.raises(HTTPException) as exc:
        await create_user_service(db_session, user_in, super_admin_user)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_create_user_super_admin_cannot_create_super_admin(db_session, super_admin_user):
    user_in = UserCreate(email="sa@example.com", password=TEST_PASSWORD, role=Role.SUPER_ADMIN)
    with pytest.raises(HTTPException) as exc:
        await create_user_service(db_session, user_in, super_admin_user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_user_admin_cannot_create_admin(db_session, admin_user):
    user_in = UserCreate(email="other@example.com", password=TEST_PASSWORD, role=Role.ADMIN)
    with pytest.raises(HTTPException) as exc:
        await create_user_service(db_session, user_in, admin_user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_user_admin_cannot_create_super_admin(db_session, admin_user):
    user_in = UserCreate(email="sa2@example.com", password=TEST_PASSWORD, role=Role.SUPER_ADMIN)
    with pytest.raises(HTTPException) as exc:
        await create_user_service(db_session, user_in, admin_user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_user_seller_forbidden(db_session, seller_user):
    user_in = UserCreate(email="y@example.com", password=TEST_PASSWORD, role=Role.SELLER)
    with pytest.raises(HTTPException) as exc:
        await create_user_service(db_session, user_in, seller_user)
    assert exc.value.status_code == 403


# --------------------------------------------------------------------------- #
# authenticate_user
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_authenticate_user_success(db_session, admin_user):
    user_in = UserCreate(email="auth@example.com", password=TEST_PASSWORD, role=Role.SELLER)
    await create_user_service(db_session, user_in, admin_user)
    user = await authenticate_user(db_session, "auth@example.com", TEST_PASSWORD)
    assert user is not None
    assert user.email == "auth@example.com"


@pytest.mark.asyncio
async def test_authenticate_user_wrong_password(db_session, admin_user):
    user_in = UserCreate(email="wrong@example.com", password=TEST_PASSWORD, role=Role.SELLER)
    await create_user_service(db_session, user_in, admin_user)
    assert await authenticate_user(db_session, "wrong@example.com", "incorrect") is None


@pytest.mark.asyncio
async def test_authenticate_user_inactive_raises(db_session, admin_user):
    user_in = UserCreate(email="inactive@example.com", password=TEST_PASSWORD, role=Role.SELLER)
    user = await create_user_service(db_session, user_in, admin_user)
    user.is_active = False
    await db_session.commit()
    with pytest.raises(HTTPException) as exc:
        await authenticate_user(db_session, "inactive@example.com", TEST_PASSWORD)
    assert exc.value.status_code == 403

