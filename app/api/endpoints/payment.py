from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import require_superadmin_or_admin, get_current_user
from app.db import get_db
from app.models.payment import Payment
from app.models.enums import PaymentDirection
from app.models.user import User
from app.schemas.payment import PaymentCreate, PaymentOut, PaymentOutPaginate
from app.services.payment import record_payment

router = APIRouter(prefix="/payments", tags=["payment"])


@router.post("", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payload: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_or_admin),
):
    try:
        payment = await record_payment(db, payload, current_user.id)
        await db.commit()
        await db.refresh(payment)
        return payment
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


@router.get("", response_model=PaymentOutPaginate)
async def list_payments(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    party_id: int | None = Query(None),
    direction: PaymentDirection | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(Payment)
    count_stmt = select(func.count()).select_from(Payment)

    if party_id is not None:
        stmt = stmt.where(Payment.party_id == party_id)
        count_stmt = count_stmt.where(Payment.party_id == party_id)
    if direction is not None:
        stmt = stmt.where(Payment.direction == direction)
        count_stmt = count_stmt.where(Payment.direction == direction)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Payment.payment_date.desc()).offset(skip).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    return PaymentOutPaginate(total=total, page=(skip // limit) + 1, size=len(items), items=items)


@router.get("/{id}", response_model=PaymentOut)
async def get_payment(id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    result = await db.execute(select(Payment).where(Payment.id == id))
    payment = result.scalars().first()
    if not payment:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    return payment


# No update/delete - a payment writes a ledger entry (or, for a walk-in,
# is the terminal event) the moment it's created. If one was entered
# wrong, reverse it with an equal-and-opposite payment rather than
# mutating history.
