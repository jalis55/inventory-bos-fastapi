from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.enums import LedgerRefType


class PartyLedgerEntryConfig(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PartyLedgerEntryOut(PartyLedgerEntryConfig):
    """
    Read-only, like StockMovementOut. There is no Create schema here on
    purpose - a PartyLedgerEntry is never written directly by a client,
    only ever inserted by a service (receive purchase, complete sale,
    record payment, process a return) inside the same transaction as the
    business event that caused it. Exposing a public create endpoint for
    this table would let a balance be set with no transaction to explain
    it - exactly what this table exists to prevent.

    Sign convention (document this once and keep it consistent everywhere
    it's used): for a SUPPLIER, credit = you owe them more (a purchase),
    debit = you owe them less (a payment out, or a purchase return). For a
    CUSTOMER, debit = they owe you more (a sale), credit = they owe you
    less (a payment in, or a sales return).
    """
    id: str
    party_id: int
    ref_type: LedgerRefType
    ref_id: str                    # polymorphic - id of the Purchase/Sale/Return/Payment/etc that caused this entry
    debit: Decimal
    credit: Decimal
    balance_after: Decimal         # snapshot of party.balance_cached immediately after this entry
    entry_date: datetime
    notes: Optional[str] = None


class PartyLedgerEntryOutPaginate(PartyLedgerEntryConfig):
    total: int
    page: int
    size: int
    items: list[PartyLedgerEntryOut]
