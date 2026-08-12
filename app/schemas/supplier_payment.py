from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date

from app.schemas.auth import UserMinimal
from app.schemas.supplier import SupplierOut
from app.models.supplier_payment import PaymentType


class BatchMinimal(BaseModel):
    id: int
    batch_number: str | None
    product_id: int
    received_quantity: int
    unit_price: float

    model_config = ConfigDict(from_attributes=True)


class SupplierPaymentCreate(BaseModel):
    supplier_id: int
    batch_id: int | None = None
    payment_type: PaymentType = PaymentType.PAYMENT
    amount: float = Field(..., gt=0)
    payment_date: date
    payment_method: str | None = Field(None, max_length=50)
    reference: str | None = Field(None, max_length=100)
    note: str | None = Field(None, max_length=255)

    model_config = ConfigDict(from_attributes=True)


class SupplierPaymentOut(BaseModel):
    id: int
    supplier_id: int
    batch_id: int | None
    payment_type: PaymentType
    amount: float
    payment_date: date
    payment_method: str | None
    reference: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime

    # Nested
    supplier: SupplierOut | None = None
    batch: BatchMinimal | None = None
    user: UserMinimal | None = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedSupplierPayments(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[SupplierPaymentOut]

    model_config = ConfigDict(from_attributes=True)


class SupplierPayableSummary(BaseModel):
    batch_id: int
    total_cost: float
    returned_value: float
    paid: float
    outstanding: float

    model_config = ConfigDict(from_attributes=True)


class BatchPayableBreakdown(BaseModel):
    batch_id: int
    total_cost: float
    returned_value: float
    paid: float
    outstanding: float

    model_config = ConfigDict(from_attributes=True)


class SupplierBalanceOut(BaseModel):
    """Consolidated supplier-level account balance.

    balance = total_received - total_returned - total_paid + total_collected
    Positive -> we owe the supplier; negative -> the supplier owes us.
    """

    supplier_id: int
    supplier_name: str | None = None
    total_received: float
    total_returned: float
    total_paid: float
    total_collected: float
    balance: float
    batches: list[BatchPayableBreakdown] = []

    model_config = ConfigDict(from_attributes=True)

