from datetime import date
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, Field


class InvoiceLedgerLine(BaseModel):
    variant_name: Optional[str] = None
    variant_sku: Optional[str] = None
    qty: Decimal = Decimal("0")
    rate: Decimal = Decimal("0")
    line_total: Decimal = Decimal("0")


class InvoiceLedgerTransaction(BaseModel):
    date: date
    description: str
    debit: Decimal = Field(default=Decimal("0"))
    credit: Decimal = Field(default=Decimal("0"))
    balance: Decimal


class InvoiceLedgerOut(BaseModel):
    kind: str  # "PURCHASE" | "SALE"
    id: str
    reference_no: Optional[str] = None
    invoice_date: date
    status: str
    party_id: Optional[int] = None
    party_name: Optional[str] = None
    party_type: Optional[str] = None
    total: Decimal
    amount_paid: Decimal
    returned_amount: Decimal
    outstanding: Decimal
    lines: List[InvoiceLedgerLine] = []
    transactions: List[InvoiceLedgerTransaction] = []


class InvoiceLedgerPartyInvoice(BaseModel):
    invoice_kind: str  # "PURCHASE" | "SALE"
    id: str
    reference_no: Optional[str] = None
    invoice_date: date
    status: str
    total: Decimal
    amount_paid: Decimal
    returned_amount: Decimal
    outstanding: Decimal


class InvoiceLedgerPartyOut(BaseModel):
    kind: str = "PARTY"
    party_id: int
    party_name: str
    party_type: str
    invoices: List[InvoiceLedgerPartyInvoice] = []