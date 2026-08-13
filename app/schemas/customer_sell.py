from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date

from app.models.customer_sell import CustomerSellStatus
from app.schemas.auth import UserMinimal
from app.schemas.customer import CustomerOut


class BatchRef(BaseModel):
    id: int
    batch_number: str | None
    product_id: int
    quantity: int
    sell_price: float

    model_config = ConfigDict(from_attributes=True)


class CustomerSellItemCreate(BaseModel):
    batch_id: int
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)

    model_config = ConfigDict(from_attributes=True)


class CustomerSellCreate(BaseModel):
    customer_id: int
    sell_date: date
    note: str | None = Field(None, max_length=255)
    items: list[CustomerSellItemCreate] = Field(..., min_length=1)

    model_config = ConfigDict(from_attributes=True)


class CustomerSellItemOut(BaseModel):
    id: int
    batch_id: int
    quantity: int
    unit_price: float
    created_at: datetime

    batch: BatchRef | None = None

    model_config = ConfigDict(from_attributes=True)


class CustomerSellOut(BaseModel):
    id: int
    sell_number: str
    customer_id: int
    sell_date: date
    note: str | None
    status: CustomerSellStatus
    created_at: datetime
    updated_at: datetime

    # Nested
    customer: CustomerOut | None = None
    user: UserMinimal | None = None
    items: list[CustomerSellItemOut] = []

    model_config = ConfigDict(from_attributes=True)


class PaginatedCustomerSells(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[CustomerSellOut]

    model_config = ConfigDict(from_attributes=True)
