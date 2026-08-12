from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.supplier import Supplier
from app.models.batch import Batch
from app.models.supplier_return import SupplierReturnItem
from app.models.supplier_payment import PaymentType, SupplierPayment
from app.schemas.supplier_payment import (
    SupplierPaymentCreate,
    SupplierPaymentOut,
    PaginatedSupplierPayments,
    SupplierPayableSummary,
    BatchPayableBreakdown,
    SupplierBalanceOut,
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
                SupplierPayment.batch_id == batch.id,
                SupplierPayment.payment_type == PaymentType.PAYMENT,
            )
        )
    ).scalar_one()

    return {
        "total_cost": total_cost,
        "returned_value": returned_value,
        "paid": paid,
        "outstanding": total_cost - returned_value - paid,
    }


async def _supplier_aggregates(db: AsyncSession, supplier_id: int) -> dict:
    """Supplier-level totals: received, returned, paid, collected and balance.

    balance = total_received - total_returned - total_paid + total_collected
    Positive -> we owe the supplier; negative -> the supplier owes us.
    """
    total_received = (
        await db.execute(
            select(func.coalesce(func.sum(
                Batch.received_quantity * Batch.unit_price
            ), 0)).where(Batch.supplier_id == supplier_id)
        )
    ).scalar_one()

    total_returned = (
        await db.execute(
            select(func.coalesce(func.sum(
                SupplierReturnItem.quantity
                * func.coalesce(SupplierReturnItem.unit_price, 0)
            ), 0))
            .select_from(SupplierReturnItem)
            .join(Batch, Batch.id == SupplierReturnItem.batch_id)
            .where(Batch.supplier_id == supplier_id)
        )
    ).scalar_one()

    total_paid = (
        await db.execute(
            select(func.coalesce(func.sum(SupplierPayment.amount), 0)).where(
                SupplierPayment.supplier_id == supplier_id,
                SupplierPayment.payment_type == PaymentType.PAYMENT,
            )
        )
    ).scalar_one()

    total_collected = (
        await db.execute(
            select(func.coalesce(func.sum(SupplierPayment.amount), 0)).where(
                SupplierPayment.supplier_id == supplier_id,
                SupplierPayment.payment_type == PaymentType.COLLECTION,
            )
        )
    ).scalar_one()

    balance = (
        total_received - total_returned - total_paid + total_collected
    )
    return {
        "total_received": total_received,
        "total_returned": total_returned,
        "total_paid": total_paid,
        "total_collected": total_collected,
        "balance": balance,
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


@router.get("/balance", response_model=SupplierBalanceOut)
async def supplier_balance(
    supplier_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Consolidated supplier-level account balance with per-batch detail."""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    aggregates = await _supplier_aggregates(db, supplier_id)

    batches_result = await db.execute(
        select(Batch).where(Batch.supplier_id == supplier_id).order_by(Batch.id)
    )
    batches = batches_result.scalars().all()
    breakdown = []
    for batch in batches:
        components = await _payable_components(db, batch)
        breakdown.append(BatchPayableBreakdown(batch_id=batch.id, **components))

    return SupplierBalanceOut(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        batches=breakdown,
        **aggregates,
    )


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
    """Record a supplier cash transaction (payment or collection).

    Payments are validated against the *supplier-level* balance, so a credit
    created by a return on one batch can offset dues on another batch of the
    same supplier. ``batch_id`` is optional.
    """
    supplier_result = await db.execute(
        select(Supplier).where(Supplier.id == payload.supplier_id)
    )
    if not supplier_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Supplier not found")

    batch = None
    if payload.batch_id is not None:
        batch_result = await db.execute(
            select(Batch).where(Batch.id == payload.batch_id)
        )
        batch = batch_result.scalar_one_or_none()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        if batch.supplier_id != payload.supplier_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch does not belong to the payment supplier",
            )

    aggregates = await _supplier_aggregates(db, payload.supplier_id)
    balance = aggregates["balance"]

    if payload.payment_type == PaymentType.PAYMENT:
        if balance <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot pay: supplier balance {balance:.2f} "
                    "(the supplier owes you)."
                ),
            )
        if payload.amount > balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Overpayment rejected: outstanding {balance:.2f}, "
                    f"attempted {payload.amount:.2f}"
                ),
            )
    else:  # COLLECTION
        if balance >= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot collect: the supplier has no outstanding credit "
                    "with you."
                ),
            )
        if payload.amount > -balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Over-collection rejected: supplier credit {-balance:.2f}, "
                    f"attempted {payload.amount:.2f}"
                ),
            )

    payment = SupplierPayment(
        supplier_id=payload.supplier_id,
        batch_id=payload.batch_id,
        payment_type=payload.payment_type,
        amount=payload.amount,
        payment_date=payload.payment_date,
        payment_method=payload.payment_method,
        reference=payload.reference,
        note=payload.note,
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
