from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import PaymentDirection


class PaymentConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(PaymentConfig):
    party_id: Optional[int] = Field(
        None,
        description=(
            "Null for a walk-in refund (no ongoing balance to adjust - "
            "this becomes a straight cash-out event with no matching "
            "PartyLedgerEntry). Required for any payment to/from a "
            "registered supplier or customer."
        ),
    )
    direction: PaymentDirection
    amount: Decimal = Field(..., gt=0)
    method: str = Field(..., max_length=50, description='e.g. "cash", "bkash", "bank_transfer"')
    payment_date: date
    reference_no: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)
    sales_return_id: Optional[str] = Field(
        None,
        description=(
            "Set only when this payment is a refund triggered by a "
            "walk-in sales return - links the cash-out back to the "
            "return that caused it for audit purposes."
        ),
    )


class PaymentOut(PaymentConfig):
    id: str
    party_id: Optional[int]
    direction: PaymentDirection
    amount: Decimal
    method: str
    payment_date: date
    reference_no: Optional[str]
    notes: Optional[str]
    sales_return_id: Optional[str]
    created_by: Optional[int]
    created_at: datetime


class PaymentOutPaginate(PaymentConfig):
    total: int
    page: int
    size: int
    items: list[PaymentOut]


# No PaymentUpdate / PaymentDelete - a payment writes a PartyLedgerEntry
# (or, for a walk-in, is the terminal event itself) the moment it's
# created. Editing or deleting it after the fact would leave the ledger
# telling a different story than the payment record. If a payment was
# entered wrong, reverse it with an equal-and-opposite payment rather
# than mutating history.

# TODO (optional, add later): PaymentAllocation, for splitting one
# payment across multiple specific purchases/sales rather than just
# applying it to the party's running balance. Most systems (including
# this one, for now) can skip this and treat every payment as "on
# account" - only add it if you need per-invoice reconciliation reports.
#
# class PaymentAllocationCreate(PaymentConfig):
#     payment_id: str
#     purchase_id: Optional[str] = None
#     sale_id: Optional[str] = None
#     allocated_amount: Decimal = Field(..., gt=0)
#
# class PaymentAllocationOut(PaymentConfig):
#     id: str
#     payment_id: str
#     purchase_id: Optional[str]
#     sale_id: Optional[str]
#     allocated_amount: Decimal
