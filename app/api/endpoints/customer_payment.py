from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.customer import Customer
from app.models.batch import Batch
from app.models.customer_sell import CustomerSell, CustomerSellItem
from app.models.customer_return import CustomerReturn, CustomerReturnItem
from app.models.customer_payment import CustomerPaymentType, CustomerPayment
from app.schemas.customer_payment import (
    CustomerPaymentCreate,
    CustomerPaymentOut,
    PaginatedCustomerPayments,
    BatchReceivableBreakdown,
    CustomerBalanceOut,
)
from app.api.deps import (
    get_current_user,
    require_superadmin_and_admin_and_store_keeper,
)


router = APIRouter(prefix="/customer-payments", tags=["Customer Payments"])


def _load_options():
    return (
        selectinload(CustomerPayment.customer).selectinload(Customer.user),
        selectinload(CustomerPayment.batch),
        selectinload(CustomerPayment.user),
    )


async def _customer_aggregates(db: AsyncSession, customer_id: int) -> dict:
    """Customer-level totals: sold, returned, collected, refunded, balance.

    balance = total_sold - total_returned - total_collected + total_refunded
    Positive -> customer owes us; negative -> we owe the customer.
    """
    total_sold = (
        await db.execute(
            select(func.coalesce(func.sum(
                CustomerSellItem.quantity
                * func.coalesce(CustomerSellItem.unit_price, 0)
            ), 0))
            .select_from(CustomerSellItem)
            .join(CustomerSell, CustomerSell.id == CustomerSellItem.sell_id)
            .where(CustomerSell.customer_id == customer_id)
        )
    ).scalar_one()

    total_returned = (
        await db.execute(
            select(func.coalesce(func.sum(
                CustomerReturnItem.quantity
                * func.coalesce(CustomerReturnItem.unit_price, 0)
            ), 0))
            .select_from(CustomerReturnItem)
            .join(CustomerReturn, CustomerReturn.id == CustomerReturnItem.return_id)
            .where(CustomerReturn.customer_id == customer_id)
        )
    ).scalar_one()

    total_collected = (
        await db.execute(
            select(func.coalesce(func.sum(CustomerPayment.amount), 0)).where(
                CustomerPayment.customer_id == customer_id,
                CustomerPayment.payment_type == CustomerPaymentType.COLLECTION,
            )
        )
    ).scalar_one()

    total_refunded = (
        await db.execute(
            select(func.coalesce(func.sum(CustomerPayment.amount), 0)).where(
                CustomerPayment.customer_id == customer_id,
                CustomerPayment.payment_type == CustomerPaymentType.REFUND,
            )
        )
    ).scalar_one()

    return {
        "total_sold": total_sold,
        "total_returned": total_returned,
        "total_collected": total_collected,
        "total_refunded": total_refunded,
        "balance": total_sold - total_returned - total_collected + total_refunded,
    }

async def _batch_breakdown(db: AsyncSession, customer_id: int) -> list[BatchReceivableBreakdown]:
    """Per-batch receivable breakdown for a customer's sold/returned/payment lines."""
    sell_batches = (
        await db.execute(
            select(func.distinct(CustomerSellItem.batch_id))
            .select_from(CustomerSellItem)
            .join(CustomerSell, CustomerSell.id == CustomerSellItem.sell_id)
            .where(CustomerSell.customer_id == customer_id)
        )
    ).scalars().all()
    return_batches = (
        await db.execute(
            select(func.distinct(CustomerReturnItem.batch_id))
            .select_from(CustomerReturnItem)
            .join(CustomerReturn, CustomerReturn.id == CustomerReturnItem.return_id)
            .where(CustomerReturn.customer_id == customer_id)
        )
    ).scalars().all()
    payment_batches = (
        await db.execute(
            select(func.distinct(CustomerPayment.batch_id)).where(
                CustomerPayment.customer_id == customer_id,
                CustomerPayment.batch_id.is_not(None),
            )
        )
    ).scalars().all()

    batch_ids = set(sell_batches) | set(return_batches) | set(payment_batches)
    breakdown = []
    for batch_id in batch_ids:
        sold = (
            await db.execute(
                select(func.coalesce(func.sum(
                    CustomerSellItem.quantity
                    * func.coalesce(CustomerSellItem.unit_price, 0)
                ), 0))
                .select_from(CustomerSellItem)
                .join(CustomerSell, CustomerSell.id == CustomerSellItem.sell_id)
                .where(
                    CustomerSell.customer_id == customer_id,
                    CustomerSellItem.batch_id == batch_id,
                )
            )
        ).scalar_one()

        returned = (
            await db.execute(
                select(func.coalesce(func.sum(
                    CustomerReturnItem.quantity
                    * func.coalesce(CustomerReturnItem.unit_price, 0)
                ), 0))
                .select_from(CustomerReturnItem)
                .join(CustomerReturn, CustomerReturn.id == CustomerReturnItem.return_id)
                .where(
                    CustomerReturn.customer_id == customer_id,
                    CustomerReturnItem.batch_id == batch_id,
                )
            )
        ).scalar_one()

        collected = (
            await db.execute(
                select(func.coalesce(func.sum(CustomerPayment.amount), 0)).where(
                    CustomerPayment.customer_id == customer_id,
                    CustomerPayment.batch_id == batch_id,
                    CustomerPayment.payment_type == CustomerPaymentType.COLLECTION,
                )
            )
        ).scalar_one()

        refunded = (
            await db.execute(
                select(func.coalesce(func.sum(CustomerPayment.amount), 0)).where(
                    CustomerPayment.customer_id == customer_id,
                    CustomerPayment.batch_id == batch_id,
                    CustomerPayment.payment_type == CustomerPaymentType.REFUND,
                )
            )
        ).scalar_one()

        breakdown.append(
            BatchReceivableBreakdown(
                batch_id=batch_id,
                sold_value=sold,
                returned_value=returned,
                collected=collected,
                refunded=refunded,
                outstanding=sold - returned - collected + refunded,
            )
        )

    breakdown.sort(key=lambda b: b.batch_id)
    return breakdown

@router.get("/", response_model=PaginatedCustomerPayments)
async def list_customer_payments(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    customer_id: int | None = Query(None, description="Filter by customer"),
    batch_id: int | None = Query(None, description="Filter by batch"),
):
    filters = []
    if customer_id is not None:
        filters.append(CustomerPayment.customer_id == customer_id)
    if batch_id is not None:
        filters.append(CustomerPayment.batch_id == batch_id)

    total = (
        await db.execute(select(func.count()).select_from(CustomerPayment).where(*filters))
    ).scalar_one()

    result = await db.execute(
        select(CustomerPayment)
        .options(*_load_options())
        .where(*filters)
        .order_by(CustomerPayment.id.desc())
        .offset(skip)
        .limit(limit)
    )
    items = result.scalars().all()
    return PaginatedCustomerPayments(total=total, skip=skip, limit=limit, items=items)


@router.get("/balance", response_model=CustomerBalanceOut)
async def customer_balance(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    customer_id: int = Query(...),
):
    customer = (
        await db.execute(select(Customer).where(Customer.id == customer_id))
    ).scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    aggregates = await _customer_aggregates(db, customer_id)
    breakdown = await _batch_breakdown(db, customer_id)
    return CustomerBalanceOut(
        customer_id=customer_id,
        customer_name=customer.name,
        **aggregates,
        batches=breakdown,
    )

@router.get("/{payment_id}", response_model=CustomerPaymentOut)
async def get_customer_payment(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CustomerPayment)
        .options(*_load_options())
        .where(CustomerPayment.id == payment_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Customer payment not found")
    return payment


@router.post("/", response_model=CustomerPaymentOut, status_code=status.HTTP_201_CREATED)
async def create_customer_payment(
    payload: CustomerPaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_and_admin_and_store_keeper),
):
    """Record a customer cash transaction (collection or refund).

    Collections are validated against the customer-level receivable balance, so
    a credit from a return on one batch can offset dues on another batch of the
    same customer. ``batch_id`` is optional.
    """
    customer_result = await db.execute(
        select(Customer).where(Customer.id == payload.customer_id)
    )
    if not customer_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Customer not found")

    if payload.batch_id is not None:
        batch_result = await db.execute(
            select(Batch).where(Batch.id == payload.batch_id)
        )
        if not batch_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Batch not found")

    aggregates = await _customer_aggregates(db, payload.customer_id)
    balance = aggregates["balance"]

    if payload.payment_type == CustomerPaymentType.COLLECTION:
        if balance <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot collect: the customer has no outstanding receivable "
                    f"(balance {balance:.2f})."
                ),
            )
        if payload.amount > balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Over-collection rejected: receivable {balance:.2f}, "
                    f"attempted {payload.amount:.2f}"
                ),
            )
    else:  # REFUND
        if balance >= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Cannot refund: the customer has no outstanding credit "
                    "with you."
                ),
            )
        if payload.amount > -balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Over-refund rejected: customer credit {-balance:.2f}, "
                    f"attempted {payload.amount:.2f}"
                ),
            )

    payment = CustomerPayment(
        customer_id=payload.customer_id,
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
        select(CustomerPayment)
        .options(*_load_options())
        .where(CustomerPayment.id == payment.id)
    )
    return result.scalar_one()
