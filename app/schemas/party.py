from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from decimal import Decimal
from datetime import datetime
from app.models.enums import PartyType


class PartyConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PartyCreate(PartyConfig):
    party_type: PartyType = Field(..., description="Type of the party")
    name: str = Field(..., min_length=1, description="Name of the party")
    phone: Optional[str] = Field(None, description="Phone number of the party")
    email: Optional[str] = Field(None, description="Email of the party")
    address: Optional[str] = Field(None, description="Address of the party")
    credit_limit: Decimal = Field(
        Decimal("0"), ge=0, description="Credit limit of the party"
    )
    # balance_cached intentionally NOT exposed here.
    # It's derived from party_ledger_entry and always starts at 0 on create.


class PartyUpdate(PartyConfig):
    party_type: Optional[PartyType] = None
    name: Optional[str] = Field(None, min_length=1)
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    credit_limit: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None
    # balance_cached intentionally NOT exposed here either.
    # It must only ever change via a ledger-writing operation (sale,
    # purchase, payment, return) - never a direct field edit, or you lose
    # the audit trail explaining *why* the balance changed.


class PartyOut(PartyConfig):
    id: int
    party_type: PartyType
    name: str
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    credit_limit: Decimal
    balance_cached: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PartyOutPaginate(PartyConfig):
    total: int
    page: int
    size: int
    items: list[PartyOut]


class PartyBalanceOut(PartyConfig):
    id: int
    name: str
    party_type: PartyType
    balance_cached: Decimal
    credit_limit: Decimal
    available_credit: Decimal
