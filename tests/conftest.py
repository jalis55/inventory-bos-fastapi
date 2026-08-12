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
from app.models.company import Company
from app.models.customer import Customer, CustomerType
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.supplier import Supplier
from app.models.user import Role, User
from app.models.batch import Batch
from app.models.stock_movement import StockMovement, MovementType
from app.models.supplier_return import SupplierReturn, SupplierReturnItem, SupplierReturnStatus
from app.models.supplier_payment import SupplierPayment
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
async def create_company(db_session):
    """Factory that persists a company directly (skipping the API)."""

    async def _factory(name: str, is_active: bool = True) -> Company:
        company = Company(name=name, is_active=is_active)
        db_session.add(company)
        await db_session.commit()
        await db_session.refresh(company)
        return company

    return _factory


@pytest_asyncio.fixture
async def create_product_variant(db_session):
    """Factory that persists a product variant directly (skipping the API)."""

    async def _factory(name: str, is_active: bool = True) -> ProductVariant:
        variant = ProductVariant(name=name, is_active=is_active)
        db_session.add(variant)
        await db_session.commit()
        await db_session.refresh(variant)
        return variant

    return _factory


@pytest_asyncio.fixture
async def create_product(db_session):
    """Factory that persists a product directly (skipping the API).

    The caller must pass ids for an existing company, category and variant.
    """

    async def _factory(
        name: str,
        company_id: int,
        category_id: int,
        product_variant_id: int,
        unit_of_measure: str = "piece",
        is_active: bool = True,
    ) -> Product:
        product = Product(
            name=name,
            company_id=company_id,
            category_id=category_id,
            product_variant_id=product_variant_id,
            unit_of_measure=unit_of_measure,
            is_active=is_active,
        )
        db_session.add(product)
        await db_session.commit()
        await db_session.refresh(product)
        return product

    return _factory

@pytest_asyncio.fixture
async def create_supplier(db_session):
    """Factory that persists a supplier directly (skipping the API)."""

    async def _factory(
        name: str,
        phone: str = "01123456789",
        email: str | None = None,
        is_active: bool = True,
        created_by: int | None = None,
    ) -> Supplier:
        supplier = Supplier(
            name=name,
            phone=phone,
            email=email,
            is_active=is_active,
            created_by=created_by,
        )
        db_session.add(supplier)
        await db_session.commit()
        await db_session.refresh(supplier)
        return supplier

    return _factory


@pytest_asyncio.fixture
async def create_customer(db_session):
    """Factory that persists a customer directly (skipping the API)."""

    async def _factory(
        name: str,
        phone: str = "01123456789",
        email: str | None = None,
        nid: str | None = None,
        customer_type: CustomerType = CustomerType.walk_in,
        is_active: bool = True,
        created_by: int | None = None,
    ) -> Customer:
        customer = Customer(
            name=name,
            phone=phone,
            email=email,
            nid=nid,
            customer_type=customer_type,
            is_active=is_active,
            created_by=created_by,
        )
        db_session.add(customer)
        await db_session.commit()
        await db_session.refresh(customer)
        return customer

    return _factory


@pytest_asyncio.fixture
async def create_batch(db_session):
    """Factory that persists a batch directly (skipping the API).

    Also writes the origin IN stock movement, mirroring the API behaviour.
    """

    async def _factory(
        product_id: int,
        supplier_id: int,
        received_quantity: int = 10,
        received_unit: str = "carton",
        units_per_package: int = 1,
        unit_price: float = 100.0,
        sell_price: float = 150.0,
        created_by: int | None = None,
    ) -> Batch:
        total = received_quantity * units_per_package
        batch = Batch(
            product_id=product_id,
            supplier_id=supplier_id,
            received_quantity=received_quantity,
            received_unit=received_unit,
            units_per_package=units_per_package,
            initial_quantity=total,
            quantity=total,
            unit_price=unit_price,
            sell_price=sell_price,
            created_by=created_by,
        )
        db_session.add(batch)
        await db_session.flush()
        db_session.add(
            StockMovement(
                batch_id=batch.id,
                movement_type=MovementType.IN,
                quantity=total,
                prev_quantity=0,
                current_quantity=total,
                created_by=created_by,
            )
        )
        await db_session.commit()
        await db_session.refresh(batch)
        return batch

    return _factory


@pytest_asyncio.fixture
async def create_stock_movement(db_session):
    """Factory that persists a stock movement directly (skipping the API)."""

    async def _factory(
        batch_id: int,
        movement_type: MovementType,
        quantity: int,
        prev_quantity: int = 0,
        current_quantity: int | None = None,
        reference: str | None = None,
        supplier_id: int | None = None,
        customer_id: int | None = None,
        created_by: int | None = None,
    ) -> StockMovement:
        if current_quantity is None:
            current_quantity = prev_quantity + quantity
        movement = StockMovement(
            batch_id=batch_id,
            movement_type=movement_type,
            quantity=quantity,
            prev_quantity=prev_quantity,
            current_quantity=current_quantity,
            reference=reference,
            supplier_id=supplier_id,
            customer_id=customer_id,
            created_by=created_by,
        )
        db_session.add(movement)
        await db_session.commit()
        await db_session.refresh(movement)
        return movement

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
