from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date

from app.schemas.auth import UserMinimal
from app.schemas.customer import CustomerOut
from app.schemas.customer_sell import BatchRef
from app.models.customer_payment import CustomerPaymentType


class CustomerPaymentCreate(BaseModel):
    customer_id: int
    batch_id: int | None = None
    payment_type: CustomerPaymentType = CustomerPaymentType.COLLECTION
    amount: float = Field(..., gt=0)
    payment_date: date
    payment_method: str | None = Field(None, max_length=50)
    reference: str | None = Field(None, max_length=100)
    note: str | None = Field(None, max_length=255)

    model_config = ConfigDict(from_attributes=True)


class CustomerPaymentOut(BaseModel):
    id: int
    customer_id: int
    batch_id: int | None
    payment_type: CustomerPaymentType
    amount: float
    payment_date: date
    payment_method: str | None
    reference: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime

    # Nested
    customer: CustomerOut | None = None
    batch: BatchRef | None = None
    user: UserMinimal | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedCustomerPayments(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[CustomerPaymentOut]

    model_config = ConfigDict(from_attributes=True)


class BatchReceivableBreakdown(BaseModel):
    batch_id: int
    sold_value: float
    returned_value: float
    collected: float
    refunded: float
    outstanding: float

    model_config = ConfigDict(from_attributes=True)


class CustomerBalanceOut(BaseModel):
    """Consolidated customer-level account balance.

    balance = total_sold - total_returned - total_collected + total_refunded
    Positive -> the customer owes us; negative -> we owe the customer.
    """

    customer_id: int
    customer_name: str | None = None
    total_sold: float
    total_returned: float
    total_collected: float
    total_refunded: float
    balance: float
    batches: list[BatchReceivableBreakdown] = []

    model_config = ConfigDict(from_attributes=True)
