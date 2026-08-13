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
from app.models.customer_sell import CustomerSell, CustomerSellItem, CustomerSellStatus
from app.schemas.customer_sell import (
    CustomerSellCreate,
    CustomerSellOut,
    PaginatedCustomerSells,
)
from app.api.deps import (
    get_current_user,
    require_superadmin_and_admin_and_store_keeper,
)


router = APIRouter(prefix="/sells", tags=["Customer Sells"])


def _load_options():
    return (
        selectinload(CustomerSell.customer).selectinload(Customer.user),
        selectinload(CustomerSell.user),
        selectinload(CustomerSell.items).selectinload(CustomerSellItem.batch),
    )


@router.get("/", response_model=PaginatedCustomerSells)
async def list_sells(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    customer_id: int | None = Query(None, description="Filter by customer"),
):
    filters = []
    if customer_id is not None:
        filters.append(CustomerSell.customer_id == customer_id)

    total = (
        await db.execute(select(func.count()).select_from(CustomerSell).where(*filters))
    ).scalar_one()

    result = await db.execute(
        select(CustomerSell)
        .options(*_load_options())
        .where(*filters)
        .order_by(CustomerSell.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()
    return PaginatedCustomerSells(total=total, skip=skip, limit=limit, items=items)


@router.get("/{sell_id}", response_model=CustomerSellOut)
async def get_sell(
    sell_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CustomerSell).options(*_load_options()).where(CustomerSell.id == sell_id)
    )
    sell = result.scalar_one_or_none()
    if not sell:
        raise HTTPException(status_code=404, detail="Sell not found")
    return sell


@router.post("/", response_model=CustomerSellOut, status_code=status.HTTP_201_CREATED)
async def create_sell(
    payload: CustomerSellCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_and_admin_and_store_keeper),
):
    """Create a sell and, atomically, post an OUT stock movement for every sold
    line, deducting each batch's quantity and increasing the receivable."""
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
        batch = batches.get(item.batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail=f"Batch {item.batch_id} not found")
        if batch.quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock on batch {batch.id}: on hand "
                    f"{batch.quantity}, requested sell {item.quantity}"
                ),
            )

    sell = CustomerSell(
        sell_number=f"SALE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        customer_id=payload.customer_id,
        sell_date=payload.sell_date,
        note=payload.note,
        status=CustomerSellStatus.COMPLETED,
        created_by=current_user.id,
    )
    db.add(sell)
    await db.flush()

    # Lines + OUT movements (single transaction: all-or-nothing)
    for item in payload.items:
        batch = batches[item.batch_id]
        prev_quantity = batch.quantity
        new_quantity = prev_quantity - item.quantity

        db.add(
            CustomerSellItem(
                sell_id=sell.id,
                batch_id=item.batch_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
        )
        db.add(
            StockMovement(
                batch_id=item.batch_id,
                movement_type=MovementType.OUT,
                quantity=item.quantity,
                prev_quantity=prev_quantity,
                current_quantity=new_quantity,
                customer_id=payload.customer_id,
                reference=sell.sell_number,
                created_by=current_user.id,
            )
        )
        batch.quantity = new_quantity

    await db.commit()

    result = await db.execute(
        select(CustomerSell).options(*_load_options()).where(CustomerSell.id == sell.id)
    )
    return result.scalar_one()
