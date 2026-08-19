from decimal import Decimal
from fastapi import HTTPException, status
from app.models.product_batch import ProductBatch


def record_batch_movement(batch: ProductBatch, qty_delta: Decimal) -> ProductBatch:
    """
    The ONLY sanctioned way to change ProductBatch.qty_remaining.

    qty_delta is negative for stock leaving the batch (a sale, or a
    purchase return sent back to the supplier) and positive for stock
    coming back into it (a sales return being restocked).

    This function does NOT commit the session. The caller is expected to,
    in the SAME transaction:
      1. call this function to update the batch in memory,
      2. insert the matching `stock_movement` row,
      3. insert the matching `party_ledger_entry` (if money is involved),
      4. commit once, at the end.

    Keeping all of that in one transaction is what stops qty_remaining,
    previous_qty, stock_movement, and the ledger from ever drifting out of
    sync with each other - if any one insert fails, the whole thing rolls
    back together.
    """
    new_remaining = batch.qty_remaining + qty_delta

    if new_remaining < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Insufficient stock in batch {batch.id}: "
                f"{batch.qty_remaining} remaining, movement of {qty_delta} requested"
            ),
        )

    if new_remaining > batch.qty_received:
        # Guards against a sales-return (or an adjustment) restocking more
        # than the batch originally received - a sign of a bug upstream
        # (e.g. returning against the wrong batch).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Movement would push batch {batch.id} above its original qty_received",
        )

    batch.previous_qty = batch.qty_remaining
    batch.qty_remaining = new_remaining
    return batch
