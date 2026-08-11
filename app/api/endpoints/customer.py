from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.customer import Customer
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerOut,
    PaginatedCustomers,
)
from app.api.deps import get_current_user, require_superadmin_and_admin


router = APIRouter(prefix="/customers", tags=["Customers"])


@router.get("/", response_model=PaginatedCustomers)
async def list_customers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    total = (await db.execute(select(func.count()).select_from(Customer))).scalar_one()

    result = await db.execute(
        select(Customer)
        .options(selectinload(Customer.user))
        .order_by(Customer.id)
        .offset(skip)
        .limit(limit)
    )
    customers = result.scalars().all()

    return PaginatedCustomers(
        total=total,
        skip=skip,
        limit=limit,
        items=customers,
    )


@router.get("/{customer_id}", response_model=CustomerOut)
async def get_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Customer)
        .options(selectinload(Customer.user))
        .where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    return customer


@router.post("/", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_in: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_and_admin),
):
    customer = Customer(
        **customer_in.model_dump(),
        created_by=current_user.id
    )
    db.add(customer)
    await db.commit()
    await db.refresh(customer)

    # Reload with relationship
    result = await db.execute(
        select(Customer)
        .options(selectinload(Customer.user))
        .where(Customer.id == customer.id)
    )
    return result.scalar_one()


@router.put("/{customer_id}", response_model=CustomerOut)
async def update_customer(
    customer_id: int,
    customer_in: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    result = await db.execute(
        select(Customer)
        .options(selectinload(Customer.user))
        .where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    update_data = customer_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)

    await db.commit()
    await db.refresh(customer)

    # Reload with relationship
    result = await db.execute(
        select(Customer)
        .options(selectinload(Customer.user))
        .where(Customer.id == customer.id)
    )
    return result.scalar_one()


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    result = await db.execute(select(Customer).where(Customer.id == customer_id))
    customer = result.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    await db.delete(customer)
    await db.commit()
    return {"message": "Customer deleted successfully"}