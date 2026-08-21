from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.models.sale import SaleLine
from app.models.sales_return import SalesReturn, SalesReturnLine
from app.models.product_batch import ProductBatch
from app.models.stock_movement import StockMovement
from app.models.party import Party
from app.models.payment import Payment
from app.models.enums import MovementType, LedgerRefType, PaymentDirection
from app.services.product_batch import record_batch_movement
from app.services.party_ledger import write_ledger_entry


async def create_sales_return(db: AsyncSession, payload, created_by: int | None) -> SalesReturn:
    """
    Does not commit - the router commits once, after this returns.
    unit_price is copied from the original sale_line, never accepted from
    the client. If party_id is None (walk-in), this writes a straight
    cash-refund Payment instead of a PartyLedgerEntry - there's no
    ongoing balance to adjust for a walk-in.
    """
    party = None
    if payload.party_id is not None:
        party = await db.get(Party, payload.party_id)
        if not party:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Party not found")

    sales_return = SalesReturn(
        party_id=payload.party_id,
        party=party,
        return_date=payload.return_date,
        reason=payload.reason,
        created_by=created_by,
    )
    # Pre-load the collection so appending lines later (after flush) doesn't
    # trigger a lazy load in the async context (MissingGreenlet).
    sales_return.lines = []
    db.add(sales_return)
    await db.flush()

    total = Decimal("0")
    # Per order: how much of this return applies to each affected sale, so
    # each order's returned_amount stays correct even if one return document
    # spans lines from multiple sale orders.
    sales_by_id: dict[str, "Sale"] = {}
    return_totals: dict[str, Decimal] = {}
    for line_in in payload.lines:
        sline = (await db.execute(
            select(SaleLine)
            .options(selectinload(SaleLine.sale))
            .where(SaleLine.id == line_in.sale_line_id)
        )).scalars().first()
        if not sline or sline.batch_id is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"SaleLine {line_in.sale_line_id} not found or sale not completed",
            )

        batch = (await db.execute(
            select(ProductBatch)
            .options(selectinload(ProductBatch.variant))
            .where(ProductBatch.id == sline.batch_id)
        )).scalars().first()

        record_batch_movement(batch, qty_delta=+line_in.qty)

        db.add(StockMovement(
            variant_id=sline.variant_id,
            batch_id=batch.id,
            movement_type=MovementType.SALES_RETURN_IN,
            qty=line_in.qty,
            ref_type="sales_return",
            ref_id=sales_return.id,
            qty_remaining_after=batch.qty_remaining,
        ))

        line_total = line_in.qty * sline.unit_price
        sales_return.lines.append(SalesReturnLine(
            sale_line_id=sline.id,
            batch_id=batch.id,
            batch=batch,
            qty=line_in.qty,
            unit_price=sline.unit_price,
            line_total=line_total,
            reason=getattr(line_in, 'reason', None),
        ))
        total += line_total
        sales_by_id[sline.sale_id] = sline.sale
        return_totals[sline.sale_id] = return_totals.get(sline.sale_id, Decimal("0")) + line_total

    for sale_id, rtotal in return_totals.items():
        sales_by_id[sale_id].returned_amount += rtotal

    if party is not None:
        # Reduces what they owe you (or increases what you owe them).
        write_ledger_entry(
            db, party, LedgerRefType.SALES_RETURN, sales_return.id,
            credit=total, notes=f"Sales return {sales_return.id}",
        )
    else:
        db.add(Payment(
            party_id=None,
            direction=PaymentDirection.REFUND_TO_CUSTOMER,
            amount=total,
            method="cash",
            payment_date=sales_return.return_date,
            sales_return_id=sales_return.id,
            created_by=created_by,
            notes="Auto-generated refund for walk-in sales return",
        ))

    return sales_return
