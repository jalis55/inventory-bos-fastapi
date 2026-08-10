"""
Shared pytest fixtures and test-database setup.

The app uses async SQLAlchemy, so the test suite runs against a real (but
isolated) in-memory SQLite database via ``aiosqlite`` + ``StaticPool``. This
gives genuine SQLAlchemy integration coverage without requiring PostgreSQL.

Environment variables required by ``app.core.config.Settings`` are set here
*before* any app module is imported (settings is a module-level singleton).
"""
import os

os.environ["SECRET_KEY"] = "test-secret-key-for-tests-only"
os.environ["DATABASE_URL"] = "postgresql+psycopg2://test:test@localhost/test_db"
os.environ["ASYNC_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models.category import Category
from app.models.user import Role, User
from app.utils.security import create_access_token, hash_password


@pytest_asyncio.fixture
async def test_engine():
    """Fresh in-memory engine with the full schema for every test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """An async session bound to the test database."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_engine):
    """
    FastAPI HTTP client with the ``get_db`` dependency overridden to use the
    test database. ``ASGITransport`` does not run the production lifespan, so
    no tables are created against the real engine.
    """
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with Session() as session:
            try:
                yield session
            finally:
                await session.close()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def create_user(db_session):
    """Factory that persists a user directly (skipping the API)."""

    async def _factory(
        email: str,
        password: str = "password123",
        full_name: str | None = None,
        role: Role = Role.SELLER,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=is_active,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _factory


@pytest_asyncio.fixture
async def create_category(db_session):
    """Factory that persists a category directly (skipping the API)."""

    async def _factory(name: str, is_active: bool = True) -> Category:
        category = Category(name=name, is_active=is_active)
        db_session.add(category)
        await db_session.commit()
        await db_session.refresh(category)
        return category

    return _factory


@pytest_asyncio.fixture
async def super_admin_user(create_user):
    return await create_user("superadmin@example.com", full_name="Super Admin", role=Role.SUPER_ADMIN)


@pytest_asyncio.fixture
async def admin_user(create_user):
    return await create_user("admin@example.com", full_name="Admin", role=Role.ADMIN)


@pytest_asyncio.fixture
async def store_keeper_user(create_user):
    return await create_user("keeper@example.com", full_name="Store Keeper", role=Role.STORE_KEEPER)


@pytest_asyncio.fixture
async def seller_user(create_user):
    return await create_user("seller@example.com", full_name="Seller", role=Role.SELLER)


@pytest.fixture
def auth_headers():
    """Builds a Bearer Authorization header for a given user."""

    def _make_headers(user: User) -> dict:
        token = create_access_token({"sub": user.email, "role": user.role})
        return {"Authorization": f"Bearer {token}"}

    return _make_headers
