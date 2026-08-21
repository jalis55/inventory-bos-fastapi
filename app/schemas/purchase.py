from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.models.enums import PurchaseStatus


class PurchaseConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PurchaseLineCreate(PurchaseConfig):
    variant_id: str = Field(..., description="ProductVariant UUID")
    qty: Decimal = Field(..., gt=0, description="Quantity ordered")
    unit_cost: Decimal = Field(..., gt=0, description="Cost per unit")


class PurchaseLineUpdate(PurchaseConfig):
    """Only allowed while purchase is still DRAFT."""
    variant_id: Optional[str] = None
    qty: Optional[Decimal] = Field(None, gt=0)
    unit_cost: Optional[Decimal] = Field(None, gt=0)


class PurchaseLineOut(PurchaseConfig):
    id: str
    purchase_id: str
    variant_id: str
    qty: Decimal
    unit_cost: Decimal
    line_total: Decimal
    # How much of this line is still in stock (null if not yet received /
    # batch not loaded). Used to hide sold-out lines from purchase returns.
    qty_remaining: Optional[Decimal] = None


class PurchaseCreate(PurchaseConfig):
    supplier_id: int = Field(..., description="Must be a SUPPLIER party")
    purchase_date: date
    reference_no: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None
    lines: List[PurchaseLineCreate] = Field(
        ..., min_length=1, description="At least one line is required"
    )


class PurchaseUpdate(PurchaseConfig):
    """
    Only allowed while status == DRAFT.
    Status changes (→ RECEIVED / CANCELLED) should go through dedicated
    service endpoints, not this generic update.
    """
    supplier_id: Optional[int] = None
    purchase_date: Optional[date] = None
    reference_no: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class PurchaseOut(PurchaseConfig):
    id: str
    supplier_id: int
    status: PurchaseStatus
    purchase_date: date
    reference_no: Optional[str]
    notes: Optional[str]
    created_by: Optional[int]
    created_at: datetime
    updated_at: datetime
    # Per-invoice received + returned amounts -
    # due = SUM(lines.line_total) - amount_paid - returned_amount
    amount_paid: Decimal = Decimal("0")
    returned_amount: Decimal = Decimal("0")
    lines: List[PurchaseLineOut] = []


class PurchaseOutPaginate(PurchaseConfig):
    total: int
    page: int
    size: int
    items: list[PurchaseOut]


class PurchaseReceive(PurchaseConfig):
    """Body for POST /purchases/{id}/receive"""
    pass


class PurchaseCancel(PurchaseConfig):
    """Body for POST /purchases/{id}/cancel"""
    reason: Optional[str] = Field(None, max_length=500)
