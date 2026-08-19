from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import SaleStatus


class SaleConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SaleLineCreate(SaleConfig):
    """
    Client supplies variant + qty + selling price.
    The service is responsible for FIFO-selecting the batch(es) and
    splitting into multiple SaleLine rows if needed.
    """
    variant_id: str = Field(..., description="ProductVariant UUID")
    qty: Decimal = Field(..., gt=0)
    unit_price: Decimal = Field(..., ge=0, description="Selling price per unit")


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
