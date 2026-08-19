"""
Unit tests for the authorization dependency helpers in app.api.deps.
"""
import pytest
from fastapi import HTTPException

from app.api.deps import require_roles
from app.models.user import Role, User


def _fake_user(role: Role) -> User:
    return User(email=f"{role.value}@example.com", hashed_password="x", role=role)


@pytest.mark.asyncio
async def test_require_roles_returns_user_for_matching_role():
    checker = require_roles("admin")
    user = _fake_user(Role.ADMIN)
    assert await checker(user) is user


@pytest.mark.asyncio
async def test_require_roles_accepts_any_configured_role():
    checker = require_roles("super_admin", "admin")
    assert await checker(_fake_user(Role.ADMIN)) is not None
    assert await checker(_fake_user(Role.SUPER_ADMIN)) is not None


@pytest.mark.asyncio
async def test_require_roles_rejects_non_matching_role():
    checker = require_roles("admin")
    with pytest.raises(HTTPException) as exc:
        await checker(_fake_user(Role.SELLER))
    assert exc.value.status_code == 403
    assert "Required roles" in exc.value.detail


@pytest.mark.asyncio
async def test_require_superadmin_rejects_admin():
    checker = require_roles("super_admin")
    with pytest.raises(HTTPException) as exc:
        await checker(_fake_user(Role.ADMIN))
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_require_multiple_roles_allows_storekeeper():
    checker = require_roles("super_admin", "admin", "store_keeper")
    assert await checker(_fake_user(Role.STORE_KEEPER)) is not None