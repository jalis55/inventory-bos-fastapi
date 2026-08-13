from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone

from app.db.database import get_db
from app.models.user import User
from app.models.customer import Customer
from app.models.batch import Batch
from app.models.stock_movement import StockMovement, MovementType
from app.models.customer_return import CustomerReturn, CustomerReturnItem, CustomerReturnStatus
from app.schemas.customer_return import (
    CustomerReturnCreate,
    CustomerReturnOut,
    PaginatedCustomerReturns,
)
from app.api.deps import (
    get_current_user,
    require_superadmin_and_admin_and_store_keeper,
)


router = APIRouter(prefix="/customer-returns", tags=["Customer Returns"])


def _load_options():
    return (
        selectinload(CustomerReturn.customer).selectinload(Customer.user),
        selectinload(CustomerReturn.user),
        selectinload(CustomerReturn.items).selectinload(CustomerReturnItem.batch),
    )


@router.get("/", response_model=PaginatedCustomerReturns)
async def list_customer_returns(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    customer_id: int | None = Query(None, description="Filter by customer"),
):
    filters = []
    if customer_id is not None:
        filters.append(CustomerReturn.customer_id == customer_id)

    total = (
        await db.execute(select(func.count()).select_from(CustomerReturn).where(*filters))
    ).scalar_one()

    result = await db.execute(
        select(CustomerReturn)
        .options(*_load_options())
        .where(*filters)
        .order_by(CustomerReturn.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()
    return PaginatedCustomerReturns(total=total, skip=skip, limit=limit, items=items)


@router.get("/{return_id}", response_model=CustomerReturnOut)
async def get_customer_return(
    return_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CustomerReturn)
        .options(*_load_options())
        .where(CustomerReturn.id == return_id)
    )
    customer_return = result.scalar_one_or_none()
    if not customer_return:
        raise HTTPException(status_code=404, detail="Customer return not found")
    return customer_return


@router.post("/", response_model=CustomerReturnOut, status_code=status.HTTP_201_CREATED)
async def create_customer_return(
    payload: CustomerReturnCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_and_admin_and_store_keeper),
):
    """Create a customer return and, atomically, post an IN stock movement for
    every returned line (restocking each batch) and reduce the receivable."""
    customer_result = await db.execute(
        select(Customer).where(Customer.id == payload.customer_id)
    )
    if not customer_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Customer not found")

    # Validate all batches up front before mutating anything.
    batch_ids = {item.batch_id for item in payload.items}
    batch_result = await db.execute(select(Batch).where(Batch.id.in_(batch_ids)))
    batches = {b.id: b for b in batch_result.scalars().all()}

    for item in payload.items:
        if item.batch_id not in batches:
            raise HTTPException(
                status_code=404, detail=f"Batch {item.batch_id} not found"
            )

    customer_return = CustomerReturn(
        return_number=f"CR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        customer_id=payload.customer_id,
        return_date=payload.return_date,
        reason=payload.reason,
        status=CustomerReturnStatus.COMPLETED,
        created_by=current_user.id,
    )
    db.add(customer_return)
    await db.flush()

    # Lines + IN movements (single transaction: all-or-nothing)
    for item in payload.items:
        batch = batches[item.batch_id]
        prev_quantity = batch.quantity
        new_quantity = prev_quantity + item.quantity

        db.add(
            CustomerReturnItem(
                return_id=customer_return.id,
                batch_id=item.batch_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
        )
        db.add(
            StockMovement(
                batch_id=item.batch_id,
                movement_type=MovementType.IN,
                quantity=item.quantity,
                prev_quantity=prev_quantity,
                current_quantity=new_quantity,
                customer_id=payload.customer_id,
                reference=customer_return.return_number,
                created_by=current_user.id,
            )
        )
        batch.quantity = new_quantity

    await db.commit()

    result = await db.execute(
        select(CustomerReturn)
        .options(*_load_options())
        .where(CustomerReturn.id == customer_return.id)
    )
    return result.scalar_one()
