from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.types import String

from app.api.deps import require_superadmin_or_admin_or_storekeeper, get_current_user
from app.db import get_db
from app.models.sales_return import SalesReturn, SalesReturnLine
from app.models.product_batch import ProductBatch
from app.models.party import Party
from app.models.user import User
from app.schemas.sales_return import (
    SalesReturnCreate, SalesReturnOut, SalesReturnOutPaginate,
)
from app.services.sales_return import create_sales_return

router = APIRouter(prefix="/sales-returns", tags=["sales-return"])


@router.post("", response_model=SalesReturnOut, status_code=status.HTTP_201_CREATED)
async def create_return(
    payload: SalesReturnCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_or_admin_or_storekeeper),
):
    try:
        sales_return = await create_sales_return(db, payload, current_user.id)
        await db.commit()
        # The service appends lines + sets relationships on the object, so it's
        # ready to serialize directly (expire_on_commit=False). A db.refresh()
        # here would expire those attrs -> MissingGreenlet on serialization.
        return sales_return
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.get("", response_model=SalesReturnOutPaginate)
async def list_returns(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    party_id: int | None = Query(None, description="Omit to include walk-in returns too"),
    search: str | None = Query(
        None,
        description="Match customer id / name / email / phone or a return id prefix",
    ),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = (
        select(SalesReturn)
        .options(
            selectinload(SalesReturn.party),
            selectinload(SalesReturn.lines)
            .selectinload(SalesReturnLine.batch)
            .selectinload(ProductBatch.variant),
        )
    )
    count_stmt = select(func.count()).select_from(SalesReturn)

    if party_id is not None:
        stmt = stmt.where(SalesReturn.party_id == party_id)
        count_stmt = count_stmt.where(SalesReturn.party_id == party_id)

    if search:
        term = f"%{search.strip()}%"
        cond = or_(
            func.cast(SalesReturn.party_id, String).ilike(term),
            func.cast(SalesReturn.id, String).ilike(term),
            Party.name.ilike(term),
            func.coalesce(Party.email, "").ilike(term),
            func.coalesce(Party.phone, "").ilike(term),
        )
        stmt = stmt.outerjoin(Party, Party.id == SalesReturn.party_id).where(cond)
        count_stmt = count_stmt.outerjoin(Party, Party.id == SalesReturn.party_id).where(cond)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(SalesReturn.return_date.desc()).offset(skip).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    return SalesReturnOutPaginate(total=total, page=(skip // limit) + 1, size=len(items), items=items)


@router.get("/{id}", response_model=SalesReturnOut)
async def get_return(id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(SalesReturn)
        .options(
            selectinload(SalesReturn.party),
            selectinload(SalesReturn.lines)
            .selectinload(SalesReturnLine.batch)
            .selectinload(ProductBatch.variant),
        )
        .where(SalesReturn.id == id)
    )
    sales_return = result.scalars().first()
    if not sales_return:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sales return not found")
    return sales_return


# No PUT/DELETE - same reasoning as purchase returns. A walk-in return
# has also already triggered a Payment refund by this point - see
# app/services/sales_return.py.
