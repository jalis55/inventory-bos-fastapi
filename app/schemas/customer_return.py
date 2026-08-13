from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date

from app.models.customer_return import CustomerReturnStatus
from app.schemas.auth import UserMinimal
from app.schemas.customer import CustomerOut
from app.schemas.customer_sell import BatchRef


class CustomerReturnItemCreate(BaseModel):
    batch_id: int
    quantity: int = Field(..., gt=0)
    unit_price: float | None = Field(None, ge=0)

    model_config = ConfigDict(from_attributes=True)


class CustomerReturnCreate(BaseModel):
    customer_id: int
    return_date: date
    reason: str | None = Field(None, max_length=255)
    items: list[CustomerReturnItemCreate] = Field(..., min_length=1)

    model_config = ConfigDict(from_attributes=True)


class CustomerReturnItemOut(BaseModel):
    id: int
    batch_id: int
    quantity: int
    unit_price: float | None
    created_at: datetime

    batch: BatchRef | None = None

    model_config = ConfigDict(from_attributes=True)


class CustomerReturnOut(BaseModel):
    id: int
    return_number: str
    customer_id: int
    return_date: date
    reason: str | None
    status: CustomerReturnStatus
    created_at: datetime
    updated_at: datetime

    # Nested
    customer: CustomerOut | None = None
    user: UserMinimal | None = None
    items: list[CustomerReturnItemOut] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedCustomerReturns(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[CustomerReturnOut]

    model_config = ConfigDict(from_attributes=True)
