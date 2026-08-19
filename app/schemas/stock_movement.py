from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MovementType


class StockMovementConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StockMovementOut(StockMovementConfig):
    """
    Read-only. StockMovement is append-only — never created/updated
    directly by a client. Always produced by a service (receive purchase,
    complete sale, adjustment, etc.).
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


class StockMovementOutPaginate(StockMovementConfig):
    total: int
    page: int
    size: int
    items: list[StockMovementOut]
