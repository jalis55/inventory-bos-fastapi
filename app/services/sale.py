from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.sale import Sale, SaleLine
from app.models.product_batch import ProductBatch
from app.models.stock_movement import StockMovement
from app.models.party import Party
from app.models.enums import MovementType, LedgerRefType, SaleStatus
from app.services.product_batch import record_batch_movement
from app.services.party_ledger import write_ledger_entry


async def complete_sale(db: AsyncSession, sale: Sale, performed_by: int | None) -> Sale:
    """
    DRAFT -> COMPLETED. Each draft line (batch_id still NULL) is
    FIFO-allocated across one or more batches - if a single batch can't
    cover the requested qty, the draft line is replaced by multiple final
    SaleLine rows, one per batch actually consumed. This is where
    record_batch_movement() gets called for real for the first time.

    Writes one StockMovement per batch touched, and (only if the sale has
    a party) ONE PartyLedgerEntry for the whole sale. Does not commit -
    the caller commits once, after this returns.
    """
    draft_lines = list(sale.lines)
    final_lines: list[SaleLine] = []
    total = Decimal("0")

    for draft in draft_lines:
        remaining = draft.qty

        # If the user pinned a specific batch (chosen supplier), draw ONLY
        # from that batch; otherwise FIFO across all available batches.
        if draft.batch_id:
            batch_result = await db.execute(
                select(ProductBatch).where(ProductBatch.id == draft.batch_id)
            )
            chosen = batch_result.scalars().first()
            if not chosen or chosen.variant_id != draft.variant_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Chosen batch {draft.batch_id} does not belong to variant {draft.variant_id}",
                )
            batches = [chosen] if chosen.qty_remaining > 0 else []
        else:
            batches_result = await db.execute(
                select(ProductBatch)
                .where(ProductBatch.variant_id == draft.variant_id, ProductBatch.qty_remaining > 0)
                .order_by(ProductBatch.received_date.asc(), ProductBatch.id.asc())
            )
            batches = batches_result.scalars().all()

        for batch in batches:
            if remaining <= 0:
                break
            take = min(remaining, batch.qty_remaining)

            record_batch_movement(batch, qty_delta=-take)

            db.add(StockMovement(
                variant_id=draft.variant_id,
                batch_id=batch.id,
                movement_type=MovementType.SALE_OUT,
                qty=take,
                ref_type="sale",
                ref_id=sale.id,
                qty_remaining_after=batch.qty_remaining,
            ))

            line_total = take * draft.unit_price
            final_lines.append(SaleLine(
                sale_id=sale.id,
                variant_id=draft.variant_id,
                batch_id=batch.id,
                qty=take,
                unit_price=draft.unit_price,
                unit_cost_snapshot=batch.cost_price,
                # line_total is DB-generated (qty * unit_price) - never set from Python
            ))
            total += line_total
            remaining -= take

        if remaining > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Insufficient stock for variant {draft.variant_id}: "
                    f"only {draft.qty - remaining} of {draft.qty} could be allocated"
                ),
            )

    # Replace the draft (unallocated) lines with the final, batch-allocated
    # ones. We ALSO rebuild the in-memory sale.lines collection so the caller
    # can serialize the sale right after commit without re-querying (a
    # same-session re-query would return the stale draft objects instead).
    for draft in draft_lines:
        await db.delete(draft)
    await db.flush()
    for final in final_lines:
        final.sale = sale
        db.add(final)
    sale.lines = final_lines

    if sale.party_id is not None:
        party = await db.get(Party, sale.party_id)
        write_ledger_entry(
            db, party, LedgerRefType.SALE, sale.id,
            debit=total, notes=f"Sale {sale.id} completed",
        )

    sale.status = SaleStatus.COMPLETED
    return sale
