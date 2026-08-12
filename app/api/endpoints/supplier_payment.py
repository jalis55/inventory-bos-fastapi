from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.supplier import Supplier
from app.models.batch import Batch
from app.models.supplier_return import SupplierReturnItem
from app.models.supplier_payment import SupplierPayment
from app.schemas.supplier_payment import (
    SupplierPaymentCreate,
    SupplierPaymentOut,
    PaginatedSupplierPayments,
    SupplierPayableSummary,
)
from app.api.deps import (
    get_current_user,
    require_superadmin_and_admin_and_store_keeper,
)


router = APIRouter(prefix="/supplier-payments", tags=["Supplier Payments"])


def _load_options():
    return (
        selectinload(SupplierPayment.supplier).selectinload(Supplier.user),
        selectinload(SupplierPayment.batch),
        selectinload(SupplierPayment.user),
    )


async def _payable_components(db: AsyncSession, batch: Batch) -> dict:
    """total_cost, returned_value, paid for a batch."""
    total_cost = batch.received_quantity * batch.unit_price

    returned_value = (
        await db.execute(
            select(func.coalesce(func.sum(
                SupplierReturnItem.quantity
                * func.coalesce(SupplierReturnItem.unit_price, 0)
            ), 0)).where(SupplierReturnItem.batch_id == batch.id)
        )
    ).scalar_one()

    paid = (
        await db.execute(
            select(func.coalesce(func.sum(SupplierPayment.amount), 0)).where(
                SupplierPayment.batch_id == batch.id
            )
        )
    ).scalar_one()

    return {
        "total_cost": total_cost,
        "returned_value": returned_value,
        "paid": paid,
        "outstanding": total_cost - returned_value - paid,
    }


@router.get("/", response_model=PaginatedSupplierPayments)
async def list_supplier_payments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    batch_id: int | None = Query(None),
    supplier_id: int | None = Query(None),
):
    filters = []
    if batch_id is not None:
        filters.append(SupplierPayment.batch_id == batch_id)
    if supplier_id is not None:
        filters.append(SupplierPayment.supplier_id == supplier_id)

    total = (
        await db.execute(
            select(func.count()).select_from(SupplierPayment).where(*filters)
        )
    ).scalar_one()
    result = await db.execute(
        select(SupplierPayment)
        .options(*_load_options())
        .where(*filters)
        .order_by(SupplierPayment.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()
    return PaginatedSupplierPayments(total=total, skip=skip, limit=limit, items=items)


@router.get("/summary", response_model=SupplierPayableSummary)
async def supplier_payment_summary(
    batch_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Batch).where(Batch.id == batch_id))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    components = await _payable_components(db, batch)
    return SupplierPayableSummary(batch_id=batch.id, **components)


@router.get("/{payment_id}", response_model=SupplierPaymentOut)
async def get_supplier_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(SupplierPayment)
        .options(*_load_options())
        .where(SupplierPayment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Supplier payment not found")
    return payment


@router.post("/", response_model=SupplierPaymentOut, status_code=status.HTTP_201_CREATED)
async def create_supplier_payment(
    payload: SupplierPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_and_admin_and_store_keeper),
):
    supplier_result = await db.execute(
        select(Supplier).where(Supplier.id == payload.supplier_id)
    )
    if not supplier_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Supplier not found")

    batch_result = await db.execute(select(Batch).where(Batch.id == payload.batch_id))
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.supplier_id != payload.supplier_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch does not belong to the payment supplier",
        )

    components = await _payable_components(db, batch)
    outstanding = components["outstanding"]
    if payload.amount > outstanding:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Overpayment rejected: outstanding {outstanding:.2f}, "
                f"attempted {payload.amount:.2f}"
            ),
        )

    payment = SupplierPayment(
        **payload.model_dump(),
        created_by=current_user.id,
    )
    db.add(payment)
    await db.commit()

    result = await db.execute(
        select(SupplierPayment)
        .options(*_load_options())
        .where(SupplierPayment.id == payment.id)
    )
    return result.scalar_one()
