from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class SalesReturnConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ─── Line schemas ────────────────────────────────────────────────────────────

class SalesReturnLineCreate(SalesReturnConfig):
    """
    Same principle as PurchaseReturnLineCreate: sale_line_id identifies
    the original line, which pins down the batch to restock and the price
    that was actually charged. unit_price is never accepted here - the
    service copies it from sale_line.unit_price.
    """
    sale_line_id: str = Field(..., description="Original SaleLine this return is against")
    qty: Decimal = Field(..., gt=0, description="Quantity the customer is returning")


class SalesReturnLineOut(SalesReturnConfig):
    id: str
    sales_return_id: str
    sale_line_id: str
    batch_id: str                # stock goes back into the SAME batch it left
    variant_id: Optional[str] = None
    variant_name: Optional[str] = None
    variant_sku: Optional[str] = None
    qty: Decimal
    unit_price: Decimal          # copied from sale_line.unit_price
    line_total: Decimal          # qty * unit_price


# ─── SalesReturn schemas ──────────────────────────────────────────────────────

class SalesReturnCreate(SalesReturnConfig):
    party_id: Optional[int] = Field(
        None,
        description=(
            "Null for a walk-in return. The service handles a null party_id "
            "as a straight cash refund (a Payment row) rather than a "
            "PartyLedgerEntry, since there's no ongoing balance to adjust."
        ),
    )
    return_date: date
    reason: Optional[str] = Field(None, max_length=500)
    lines: List[SalesReturnLineCreate] = Field(
        ..., min_length=1, description="At least one line is required"
    )


class SalesReturnOut(SalesReturnConfig):
    id: str
    party_id: Optional[int]
    party_name: Optional[str] = None
    return_date: date
    reason: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    lines: List[SalesReturnLineOut] = []


class SalesReturnOutPaginate(SalesReturnConfig):
    total: int
    page: int
    size: int
    items: list[SalesReturnOut]


# No SalesReturnUpdate - same reasoning as PurchaseReturn: a completed
# return has already moved stock and (for registered parties) the ledger,
# or (for walk-ins) triggered a cash refund. Not safely editable after
# the fact.
