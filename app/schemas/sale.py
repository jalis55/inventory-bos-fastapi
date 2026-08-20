from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import SaleStatus


class SaleConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SaleLineCreate(SaleConfig):
    """
    Client supplies variant + qty + selling price. Optionally a specific
    batch_id (=> a specific supplier's stock, since each batch carries its
    own supplier + cost_price); leave blank to let the service FIFO-select
    across all available batches.
    """
    variant_id: str = Field(..., description="ProductVariant UUID")
    qty: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0, description="Selling price per unit")
    batch_id: Optional[str] = Field(None, description="Optional chosen batch/supplier")


class SaleLineOut(SaleConfig):
    id: str
    sale_id: str
    variant_id: str
    batch_id: Optional[str]
    qty: Decimal
    unit_price: Decimal
    unit_cost_snapshot: Optional[Decimal]
    line_total: Decimal


class SaleCreate(SaleConfig):
    party_id: Optional[int] = Field(None, description="Null = walk-in / cash customer")
    sale_date: date
    lines: List[SaleLineCreate] = Field(
        ..., min_length=1, description="At least one line is required"
    )


class SaleUpdate(SaleConfig):
    """
    Only allowed while status == DRAFT.
    Status transitions go through dedicated endpoints.
    """
    party_id: Optional[int] = None
    sale_date: Optional[date] = None


class SaleOut(SaleConfig):
    id: str
    party_id: Optional[int]
    status: SaleStatus
    sale_date: date
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    # Per-order received + returned amounts -
    # outstanding = SUM(lines.line_total) - amount_paid - returned_amount
    amount_paid: Decimal = Decimal("0")
    returned_amount: Decimal = Decimal("0")
    lines: List[SaleLineOut] = []


class SaleOutPaginate(SaleConfig):
    total: int
    page: int
    size: int
    items: list[SaleOut]


class SaleComplete(SaleConfig):
    """Body for POST /sales/{id}/complete"""
    pass


class SaleCancel(SaleConfig):
    """Body for POST /sales/{id}/cancel"""
    reason: Optional[str] = Field(None, max_length=500)
