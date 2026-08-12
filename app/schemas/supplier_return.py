from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date

from app.models.supplier_return import SupplierReturnStatus
from app.schemas.auth import UserMinimal
from app.schemas.supplier import SupplierOut


class SupplierReturnItemCreate(BaseModel):
    batch_id: int
    quantity: int = Field(..., gt=0)
    unit_price: float | None = Field(None, ge=0)

    model_config = ConfigDict(from_attributes=True)


class SupplierReturnCreate(BaseModel):
    supplier_id: int
    return_date: date
    reason: str | None = Field(None, max_length=255)
    items: list[SupplierReturnItemCreate] = Field(..., min_length=1)

    model_config = ConfigDict(from_attributes=True)


class SupplierReturnItemOut(BaseModel):
    id: int
    batch_id: int
    quantity: int
    unit_price: float | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SupplierReturnOut(BaseModel):
    id: int
    return_number: str
    supplier_id: int
    return_date: date
    reason: str | None
    status: SupplierReturnStatus
    created_at: datetime
    updated_at: datetime

    # Nested
    supplier: SupplierOut | None = None
    user: UserMinimal | None = None
    items: list[SupplierReturnItemOut] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedSupplierReturns(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[SupplierReturnOut]

    model_config = ConfigDict(from_attributes=True)
