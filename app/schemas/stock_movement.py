from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

from app.models.stock_movement import MovementType
from app.schemas.auth import UserMinimal


class BatchMinimal(BaseModel):
    """Lightweight batch reference used inside a stock movement response."""

    id: int
    product_id: int
    batch_number: str | None
    quantity: int

    model_config = ConfigDict(from_attributes=True)


class StockMovementCreate(BaseModel):
    batch_id: int
    movement_type: MovementType
    quantity: int = Field(..., gt=0)
    reference: str | None = Field(None, max_length=100)
    reverses_id: int | None = None
    supplier_id: int | None = None
    customer_id: int | None = None

    model_config = ConfigDict(from_attributes=True)


class StockMovementOut(BaseModel):
    id: int
    batch_id: int
    movement_type: MovementType
    quantity: int
    prev_quantity: int
    current_quantity: int
    reference: str | None
    reverses_id: int | None
    supplier_id: int | None
    customer_id: int | None
    created_at: datetime
    updated_at: datetime

    # Nested
    batch: BatchMinimal | None = None
    user: UserMinimal | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedStockMovements(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[StockMovementOut]

    model_config = ConfigDict(from_attributes=True)
