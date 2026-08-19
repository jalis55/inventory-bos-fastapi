from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.purchase import Purchase
from app.models.product_batch import ProductBatch
from app.models.stock_movement import StockMovement
from app.models.party import Party
from app.models.enums import MovementType, LedgerRefType, PurchaseStatus
from app.services.party_ledger import write_ledger_entry


async def receive_purchase(
    db: AsyncSession, purchase: Purchase, performed_by: int | None
) -> Purchase:
    """
    DRAFT -> RECEIVED. For every line: creates one ProductBatch (the
    strict 1:1 rule - one batch per PurchaseLine) and one
    StockMovement(PURCHASE_IN). Writes ONE PartyLedgerEntry for the whole
    purchase (credit = sum of all line_totals) rather than one per line -
    the ledger only needs transaction-level granularity, not per-line.

    Does not commit - the caller commits once, after this returns.
    """
    supplier = await db.get(Party, purchase.supplier_id)

    total = Decimal("0")
    for line in purchase.lines:
        batch = ProductBatch(
            variant_id=line.variant_id,
            purchase_line_id=line.id,
            supplier_id=purchase.supplier_id,
            cost_price=line.unit_cost,
            qty_received=line.qty,
            qty_remaining=line.qty,
            received_date=purchase.purchase_date,
        )
        db.add(batch)
        await db.flush()  # need batch.id before referencing it below

        db.add(StockMovement(
            variant_id=line.variant_id,
            batch_id=batch.id,
            movement_type=MovementType.PURCHASE_IN,
            qty=line.qty,
            ref_type="purchase",
            ref_id=purchase.id,
            qty_remaining_after=batch.qty_remaining,
        ))
        total += line.line_total

    write_ledger_entry(
        db, supplier, LedgerRefType.PURCHASE, purchase.id,
        credit=total, notes=f"Purchase {purchase.id} received",
    )

    purchase.status = PurchaseStatus.RECEIVED
    return purchase
