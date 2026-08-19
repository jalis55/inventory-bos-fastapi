from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_current_user
from app.db import get_db
from app.models.stock_movement import StockMovement
from app.models.enums import MovementType
from app.schemas.stock_movement import StockMovementOut, StockMovementOutPaginate

router = APIRouter(prefix="/stock-movements", tags=["stock-movement"])


@router.get("", response_model=StockMovementOutPaginate)
async def list_stock_movements(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    variant_id: str | None = Query(None),
    batch_id: str | None = Query(None),
    movement_type: MovementType | None = Query(None),
    ref_type: str | None = Query(None),
    ref_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Read-only audit log. No create / update / delete endpoints —
    movements are only ever written by services.
    """
    stmt = select(StockMovement)
    count_stmt = select(func.count()).select_from(StockMovement)

    if variant_id is not None:
        stmt = stmt.where(StockMovement.variant_id == variant_id)
        count_stmt = count_stmt.where(StockMovement.variant_id == variant_id)
    if batch_id is not None:
        stmt = stmt.where(StockMovement.batch_id == batch_id)
        count_stmt = count_stmt.where(StockMovement.batch_id == batch_id)
    if movement_type is not None:
        stmt = stmt.where(StockMovement.movement_type == movement_type)
        count_stmt = count_stmt.where(StockMovement.movement_type == movement_type)
    if ref_type is not None:
        stmt = stmt.where(StockMovement.ref_type == ref_type)
        count_stmt = count_stmt.where(StockMovement.ref_type == ref_type)
    if ref_id is not None:
        stmt = stmt.where(StockMovement.ref_id == ref_id)
        count_stmt = count_stmt.where(StockMovement.ref_id == ref_id)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(StockMovement.movement_date.desc())
    stmt = stmt.offset(skip).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    return StockMovementOutPaginate(
        total=total, page=(skip // limit) + 1, size=len(items), items=items,
    )


@router.get("/{id}", response_model=StockMovementOut)
async def get_stock_movement(
    id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(StockMovement).where(StockMovement.id == id))
    movement = result.scalars().first()
    if not movement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stock movement not found")
    return movement
