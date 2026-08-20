from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import require_superadmin_or_admin_or_storekeeper, get_current_user
from app.db import get_db
from app.models.purchase_return import PurchaseReturn, PurchaseReturnLine
from app.models.product_batch import ProductBatch
from app.models.user import User
from app.schemas.purchase_return import (
    PurchaseReturnCreate, PurchaseReturnOut, PurchaseReturnOutPaginate,
)
from app.services.purchase_return import create_purchase_return

router = APIRouter(prefix="/purchase-returns", tags=["purchase-return"])


@router.post("", response_model=PurchaseReturnOut, status_code=status.HTTP_201_CREATED)
async def create_return(
    payload: PurchaseReturnCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_or_admin_or_storekeeper),
):
    try:
        purchase_return = await create_purchase_return(db, payload, current_user.id)
        await db.commit()
        # The service appends lines + sets relationships on the object, so it's
        # ready to serialize directly (expire_on_commit=False). A db.refresh()
        # here would expire those attrs -> MissingGreenlet on serialization.
        return purchase_return
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.get("", response_model=PurchaseReturnOutPaginate)
async def list_returns(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    supplier_id: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = (
        select(PurchaseReturn)
        .options(
            selectinload(PurchaseReturn.supplier),
            selectinload(PurchaseReturn.lines)
            .selectinload(PurchaseReturnLine.batch)
            .selectinload(ProductBatch.variant),
        )
    )
    count_stmt = select(func.count()).select_from(PurchaseReturn)

    if supplier_id is not None:
        stmt = stmt.where(PurchaseReturn.supplier_id == supplier_id)
        count_stmt = count_stmt.where(PurchaseReturn.supplier_id == supplier_id)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(PurchaseReturn.return_date.desc()).offset(skip).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    return PurchaseReturnOutPaginate(total=total, page=(skip // limit) + 1, size=len(items), items=items)


@router.get("/{id}", response_model=PurchaseReturnOut)
async def get_return(id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(PurchaseReturn)
        .options(
            selectinload(PurchaseReturn.supplier),
            selectinload(PurchaseReturn.lines)
            .selectinload(PurchaseReturnLine.batch)
            .selectinload(ProductBatch.variant),
        )
        .where(PurchaseReturn.id == id)
    )
    purchase_return = result.scalars().first()
    if not purchase_return:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase return not found")
    return purchase_return


# No PUT/DELETE - a return has already moved stock and money (see the
# schema and model notes). Correct a mistake with a new adjustment, not
# by editing history.
