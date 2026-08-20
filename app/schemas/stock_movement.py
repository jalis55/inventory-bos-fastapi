from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MovementType


class StockMovementConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VariantBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    sku: str
    variant_name: str


class BatchBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    qty_received: Decimal
    qty_remaining: Decimal
    cost_price: Decimal
    received_date: date
    expiry_date: Optional[date]


class StockMovementOut(StockMovementConfig):
    """
    Read-only. StockMovement is append-only — never created/updated
    directly by a client. Always produced by a service (receive purchase,
    complete sale, adjustment, etc.). Includes nested variant/batch briefs
    so the UI never has to resolve raw IDs.
    """
    id: str
    variant_id: str
    batch_id: str
    movement_type: MovementType
    qty: Decimal
    ref_type: str
    ref_id: str
    qty_remaining_after: Decimal
    movement_date: datetime
    variant: VariantBrief
    batch: BatchBrief


class StockMovementOutPaginate(StockMovementConfig):
    total: int
    page: int
    size: int
    items: list[StockMovementOut]
