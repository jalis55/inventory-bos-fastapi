from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.batch import Batch
from app.models.stock_movement import StockMovement, MovementType
from app.schemas.stock_movement import (
    StockMovementCreate,
    StockMovementOut,
    PaginatedStockMovements,
)
from app.api.deps import (
    get_current_user,
    require_superadmin_and_admin_and_store_keeper,
)


router = APIRouter(prefix="/stock-movements", tags=["Stock Movements"])


@router.get("/", response_model=PaginatedStockMovements)
async def list_stock_movements(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    batch_id: int | None = Query(None, description="Filter by batch"),
):
    filters = []
    if batch_id is not None:
        filters.append(StockMovement.batch_id == batch_id)

    total = (
        await db.execute(
            select(func.count()).select_from(StockMovement).where(*filters)
        )
    ).scalar_one()

    result = await db.execute(
        select(StockMovement)
        .options(selectinload(StockMovement.batch), selectinload(StockMovement.user))
        .where(*filters)
        .order_by(StockMovement.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()

    return PaginatedStockMovements(total=total, skip=skip, limit=limit, items=items)


@router.get("/{movement_id}", response_model=StockMovementOut)
async def get_stock_movement(
    movement_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(StockMovement)
        .options(selectinload(StockMovement.batch), selectinload(StockMovement.user))
        .where(StockMovement.id == movement_id)
    )
    movement = result.scalar_one_or_none()

    if not movement:
        raise HTTPException(status_code=404, detail="Stock movement not found")

    return movement


@router.post("/", response_model=StockMovementOut, status_code=status.HTTP_201_CREATED)
async def create_stock_movement(
    movement_in: StockMovementCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_and_admin_and_store_keeper),
):
    """Create an immutable movement and apply it to the batch balance atomically.

    ``IN`` increases the batch balance, ``OUT`` and ``ADJUSTMENT`` decrease it.
    An ``OUT``/``ADJUSTMENT`` that would drive the balance below zero is rejected.
    """
    result = await db.execute(select(Batch).where(Batch.id == movement_in.batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    prev_quantity = batch.quantity
    delta = (
        movement_in.quantity
        if movement_in.movement_type == MovementType.IN
        else -movement_in.quantity
    )
    new_quantity = prev_quantity + delta

    if new_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient stock: movement would drive the batch quantity below zero",
        )

    movement = StockMovement(
        **movement_in.model_dump(),
        prev_quantity=prev_quantity,
        current_quantity=new_quantity,
        created_by=current_user.id,
    )
    batch.quantity = new_quantity

    db.add(movement)
    await db.commit()
    await db.refresh(movement)

    # Reload with relationships
    result = await db.execute(
        select(StockMovement)
        .options(selectinload(StockMovement.batch), selectinload(StockMovement.user))
        .where(StockMovement.id == movement.id)
    )
    return result.scalar_one()
