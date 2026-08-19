from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import require_superadmin_or_admin_or_storekeeper, get_current_user
from app.db import get_db
from app.models.sales_return import SalesReturn
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
        await db.refresh(sales_return, attribute_names=["lines"])
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
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(SalesReturn).options(selectinload(SalesReturn.lines))
    count_stmt = select(func.count()).select_from(SalesReturn)

    if party_id is not None:
        stmt = stmt.where(SalesReturn.party_id == party_id)
        count_stmt = count_stmt.where(SalesReturn.party_id == party_id)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(SalesReturn.return_date.desc()).offset(skip).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    return SalesReturnOutPaginate(total=total, page=(skip // limit) + 1, size=len(items), items=items)


@router.get("/{id}", response_model=SalesReturnOut)
async def get_return(id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(
        select(SalesReturn).options(selectinload(SalesReturn.lines)).where(SalesReturn.id == id)
    )
    sales_return = result.scalars().first()
    if not sales_return:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sales return not found")
    return sales_return


# No PUT/DELETE - same reasoning as purchase returns. A walk-in return
# has also already triggered a Payment refund by this point - see
# app/services/sales_return.py.
