from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from app.db.database import get_db
from app.models.user import User
from app.models.supplier import Supplier
from app.models.batch import Batch
from app.models.stock_movement import StockMovement, MovementType
from app.models.supplier_return import (
    SupplierReturn,
    SupplierReturnItem,
    SupplierReturnStatus,
)
from app.schemas.supplier_return import (
    SupplierReturnCreate,
    SupplierReturnOut,
    PaginatedSupplierReturns,
)
from app.api.deps import (
    get_current_user,
    require_superadmin_and_admin_and_store_keeper,
)


router = APIRouter(prefix="/supplier-returns", tags=["Supplier Returns"])


def _load_options():
    return (
        selectinload(SupplierReturn.supplier).selectinload(Supplier.user),
        selectinload(SupplierReturn.user),
        selectinload(SupplierReturn.items).selectinload(SupplierReturnItem.batch),
    )


@router.get("/", response_model=PaginatedSupplierReturns)
async def list_supplier_returns(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    total = (
        await db.execute(select(func.count()).select_from(SupplierReturn))
    ).scalar_one()
    result = await db.execute(
        select(SupplierReturn)
        .options(*_load_options())
        .order_by(SupplierReturn.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()
    return PaginatedSupplierReturns(total=total, skip=skip, limit=limit, items=items)


@router.get("/{return_id}", response_model=SupplierReturnOut)
async def get_supplier_return(
    return_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SupplierReturn)
        .options(*_load_options())
        .where(SupplierReturn.id == return_id)
    )
    supplier_return = result.scalar_one_or_none()

    if not supplier_return:
        raise HTTPException(status_code=404, detail="Supplier return not found")

    return supplier_return


@router.post("/", response_model=SupplierReturnOut, status_code=status.HTTP_201_CREATED)
async def create_supplier_return(
    payload: SupplierReturnCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_and_admin_and_store_keeper),
):
    """Create a supplier return and, atomically, post an OUT stock movement for
    every returned line, deducting each batch's quantity."""
    supplier_result = await db.execute(
        select(Supplier).where(Supplier.id == payload.supplier_id)
    )
    if not supplier_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Supplier not found")

    # Validate all batches up front before mutating anything.
    batch_ids = {item.batch_id for item in payload.items}
    batch_result = await db.execute(select(Batch).where(Batch.id.in_(batch_ids)))
    batches = {b.id: b for b in batch_result.scalars().all()}

    for item in payload.items:
        batch = batches.get(item.batch_id)
        if not batch:
            raise HTTPException(
                status_code=404, detail=f"Batch {item.batch_id} not found"
            )
        if batch.supplier_id != payload.supplier_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Batch {batch.id} does not belong to the return supplier",
            )
        if batch.quantity < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock on batch {batch.id}: "
                    f"on hand {batch.quantity}, requested return {item.quantity}"
                ),
            )

    # Header
    supplier_return = SupplierReturn(
        return_number=f"SR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        supplier_id=payload.supplier_id,
        return_date=payload.return_date,
        reason=payload.reason,
        status=SupplierReturnStatus.COMPLETED,
        created_by=current_user.id,
    )
    db.add(supplier_return)
    await db.flush()  # obtain id for the return items

    # Lines + OUT movements (single transaction: all-or-nothing)
    for item in payload.items:
        batch = batches[item.batch_id]
        prev_quantity = batch.quantity
        new_quantity = prev_quantity - item.quantity

        db.add(
            SupplierReturnItem(
                return_id=supplier_return.id,
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
                supplier_id=payload.supplier_id,
                reference=supplier_return.return_number,
                created_by=current_user.id,
            )
        )
        batch.quantity = new_quantity

    await db.commit()

    # Reload with relationships
    result = await db.execute(
        select(SupplierReturn)
        .options(*_load_options())
        .where(SupplierReturn.id == supplier_return.id)
    )
    return result.scalar_one()
