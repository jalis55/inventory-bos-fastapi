from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
from app.schemas.product import ProductOut
from app.schemas.supplier import SupplierOut
from app.schemas.auth import UserMinimal


class BatchCreate(BaseModel):
    product_id: int
    supplier_id: int
    batch_number: str | None = Field(None, max_length=50)
    
    received_quantity: int = Field(..., gt=0)
    received_unit: str = Field(..., min_length=1, max_length=20)  # carton, box, pcs
    units_per_package: int = Field(1, gt=0)                      # default 1 for direct pcs

    unit_price: float = Field(..., ge=0)
    sell_price: float = Field(..., ge=0)

    mfg_date: date | None = None
    exp_date: date | None = None
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)


class BatchUpdate(BaseModel):
    batch_number: str | None = Field(None, max_length=50)
    unit_price: float | None = Field(None, ge=0)
    sell_price: float | None = Field(None, ge=0)
    mfg_date: date | None = None
    exp_date: date | None = None
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class BatchOut(BaseModel):
    id: int
    product_id: int
    supplier_id: int
    batch_number: str | None

    received_quantity: int
    received_unit: str
    units_per_package: int

    initial_quantity: int
    quantity: int

    unit_price: float
    sell_price: float

    mfg_date: date | None
    exp_date: date | None

    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Nested
    product: ProductOut | None = None
    supplier: SupplierOut | None = None
    user: UserMinimal | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedBatches(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[BatchOut]

    model_config = ConfigDict(from_attributes=True)