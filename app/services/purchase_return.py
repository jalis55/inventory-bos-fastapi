from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.purchase import PurchaseLine
from app.models.purchase_return import PurchaseReturn, PurchaseReturnLine
from app.models.product_batch import ProductBatch
from app.models.stock_movement import StockMovement
from app.models.party import Party
from app.models.enums import MovementType, LedgerRefType
from app.services.product_batch import record_batch_movement
from app.services.party_ledger import write_ledger_entry


async def create_purchase_return(db: AsyncSession, payload, created_by: int | None) -> PurchaseReturn:
    """
    Does not commit - the router commits once, after this returns.
    Each line's unit_cost is copied from the batch's cost_price, never
    accepted from the client - the return amount is derived from history,
    never re-typed.
    """
    supplier = await db.get(Party, payload.supplier_id)
    if not supplier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")

    purchase_return = PurchaseReturn(
        supplier_id=payload.supplier_id,
        return_date=payload.return_date,
        reason=payload.reason,
        created_by=created_by,
    )
    db.add(purchase_return)
    await db.flush()

    total = Decimal("0")
    for line_in in payload.lines:
        pline = (await db.execute(
            select(PurchaseLine).where(PurchaseLine.id == line_in.purchase_line_id)
        )).scalars().first()
        if not pline:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                f"PurchaseLine {line_in.purchase_line_id} not found",
            )

        batch = (await db.execute(
            select(ProductBatch).where(ProductBatch.purchase_line_id == pline.id)
        )).scalars().first()
        if not batch:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"No batch exists yet for purchase line {pline.id} - purchase not received",
            )

        record_batch_movement(batch, qty_delta=-line_in.qty)

        db.add(StockMovement(
            variant_id=batch.variant_id,
            batch_id=batch.id,
            movement_type=MovementType.PURCHASE_RETURN_OUT,
            qty=line_in.qty,
            ref_type="purchase_return",
            ref_id=purchase_return.id,
            qty_remaining_after=batch.qty_remaining,
        ))

        line_total = line_in.qty * batch.cost_price
        db.add(PurchaseReturnLine(
            purchase_return_id=purchase_return.id,
            purchase_line_id=pline.id,
            batch_id=batch.id,
            qty=line_in.qty,
            unit_cost=batch.cost_price,
            line_total=line_total,
        ))
        total += line_total

    # Reduces what you owe the supplier (or increases what they owe you).
    write_ledger_entry(
        db, supplier, LedgerRefType.PURCHASE_RETURN, purchase_return.id,
        debit=total, notes=f"Purchase return {purchase_return.id}",
    )

    return purchase_return
