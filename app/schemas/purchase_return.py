from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class PurchaseReturnConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ─── Line schemas ────────────────────────────────────────────────────────────

class PurchaseReturnLineCreate(PurchaseReturnConfig):
    """
    Client only identifies WHAT is being returned and HOW MUCH -
    purchase_line_id points at the original line, which pins down the
    exact batch. unit_cost is never accepted here: the service copies it
    straight from that batch's cost_price, so a return amount can never
    drift from what was actually paid for that stock.
    """
    purchase_line_id: str = Field(..., description="Original PurchaseLine this return is against")
    qty: Decimal = Field(..., gt=0, description="Quantity being returned to the supplier")


class PurchaseReturnLineOut(PurchaseReturnConfig):
    id: str
    purchase_return_id: str
    purchase_line_id: str
    batch_id: str
    variant_id: Optional[str] = None
    variant_name: Optional[str] = None
    variant_sku: Optional[str] = None
    qty: Decimal
    unit_cost: Decimal           # copied from batch.cost_price at return time
    line_total: Decimal          # qty * unit_cost


# ─── PurchaseReturn schemas ───────────────────────────────────────────────────

class PurchaseReturnCreate(PurchaseReturnConfig):
    supplier_id: int = Field(
        ..., description="Must match the supplier on every line's original purchase"
    )
    return_date: date
    reason: Optional[str] = Field(None, max_length=500)
    lines: List[PurchaseReturnLineCreate] = Field(
        ..., min_length=1, description="At least one line is required"
    )


class PurchaseReturnOut(PurchaseReturnConfig):
    id: str
    supplier_id: int
    supplier_name: Optional[str] = None
    return_date: date
    reason: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    lines: List[PurchaseReturnLineOut] = []


class PurchaseReturnOutPaginate(PurchaseReturnConfig):
    total: int
    page: int
    size: int
    items: list[PurchaseReturnOut]


# No PurchaseReturnUpdate - a return, once created, has already moved
# stock (StockMovement) and money (PartyLedgerEntry). Editing it after the
# fact would desync those side effects from the return record itself.
# If a return was entered wrong, that's a business decision for a
# correcting adjustment, not a silent edit.
