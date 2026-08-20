from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class ProductBatchCreate(BaseModel):
    """
    Internal-shape schema. In the finished system this should only ever be
    built by the purchase-receiving service (one call per PurchaseLine
    when a Purchase moves to RECEIVED) - never accepted directly from an
    arbitrary API client. See the router for how this is currently gated.
    """
    variant_id: str
    purchase_line_id: str
    supplier_id: int
    cost_price: Decimal = Field(..., gt=0)
    qty_received: Decimal = Field(..., gt=0)
    received_date: date
    expiry_date: Optional[date] = None


class ProductBatchExpiryUpdate(BaseModel):
    # The ONLY field ever correctable post-creation - a data-entry fix,
    # not a business mutation. cost_price, qty_received, qty_remaining,
    # and previous_qty must never be edited through this or any schema.
    expiry_date: Optional[date] = None


class ProductBatchOut(BaseModel):
    id: str
    variant_id: str
    variant_name: Optional[str] = None
    variant_sku: Optional[str] = None
    purchase_line_id: str
    supplier_id: int
    supplier_name: Optional[str] = None
    cost_price: Decimal
    qty_received: Decimal
    qty_remaining: Decimal
    previous_qty: Optional[Decimal]
    received_date: date
    expiry_date: Optional[date]
    created_at: datetime

    class Config:
        from_attributes = True


class ProductBatchOutPaginate(BaseModel):
    total: int
    page: int
    size: int
    items: list[ProductBatchOut]
