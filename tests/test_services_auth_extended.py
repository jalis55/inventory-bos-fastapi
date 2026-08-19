"""
Service-layer tests for the account lockout behaviours in app.services.auth.
"""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import settings
from app.models.user import User
from app.services.auth import authenticate_user
from tests.conftest import TEST_PASSWORD


async def _fetch_user(db, email: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_authenticate_user_unknown_email_returns_none(db_session):
    result = await authenticate_user(db_session, "ghost@example.com", "WrongPass1!")
    assert result is None


@pytest.mark.asyncio
async def test_failed_attempts_are_counted(db_session, create_user):
    user = await create_user("counter@example.com", password=TEST_PASSWORD)
    for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
        assert await authenticate_user(db_session, user.email, "WrongPass1!") is None

    fresh = await _fetch_user(db_session, user.email)
    assert fresh.failed_login_attempts == settings.MAX_LOGIN_ATTEMPTS - 1
    assert fresh.locked_until is None


@pytest.mark.asyncio
async def test_account_is_locked_after_max_failed_attempts(db_session, create_user):
    user = await create_user("locks@example.com", password=TEST_PASSWORD)
    for _ in range(settings.MAX_LOGIN_ATTEMPTS):
        assert await authenticate_user(db_session, user.email, "WrongPass1!") is None

    fresh = await _fetch_user(db_session, user.email)
    assert fresh.failed_login_attempts == settings.MAX_LOGIN_ATTEMPTS
    assert fresh.locked_until is not None

    # Even the correct password is rejected while locked.
    with pytest.raises(HTTPException) as exc:
        await authenticate_user(db_session, user.email, TEST_PASSWORD)
    assert exc.value.status_code == 423


@pytest.mark.asyncio
async def test_expired_lock_resets_before_next_attempt(db_session, create_user):
    user = await create_user("expired@example.com", password=TEST_PASSWORD)
    user.failed_login_attempts = 4
    user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=5)
    await db_session.commit()

    # Wrong attempt after an expired lock -> counter restarts at 1, no lock.
    assert await authenticate_user(db_session, user.email, "WrongPass1!") is None

    fresh = await _fetch_user(db_session, user.email)
    assert fresh.failed_login_attempts == 1
    assert fresh.locked_until is None


@pytest.mark.asyncio
async def test_successful_login_clears_failure_state(db_session, create_user):
    user = await create_user("recovered@example.com", password=TEST_PASSWORD)
    user.failed_login_attempts = 4
    user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db_session.commit()

    result = await authenticate_user(db_session, user.email, TEST_PASSWORD)
    assert result is not None

    fresh = await _fetch_user(db_session, user.email)
    assert fresh.failed_login_attempts == 0
    assert fresh.locked_until is None