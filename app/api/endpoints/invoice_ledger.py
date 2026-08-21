from decimal import Decimal
from collections import defaultdict
from typing import Union
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.db import get_db
from app.models.purchase import Purchase, PurchaseLine
from app.models.sale import Sale, SaleLine
from app.models.party import Party
from app.models.purchase_return import PurchaseReturn, PurchaseReturnLine
from app.models.sales_return import SalesReturn, SalesReturnLine
from app.models.payment import Payment
from app.models.enums import PaymentDirection, PurchaseStatus, SaleStatus
from app.models.user import User
from app.schemas.invoice_ledger import (
    InvoiceLedgerLine,
    InvoiceLedgerOut,
    InvoiceLedgerPartyOut,
    InvoiceLedgerPartyInvoice,
    InvoiceLedgerTransaction,
)

router = APIRouter(prefix="/invoice-ledger", tags=["invoice-ledger"])


async def find_purchase(db: AsyncSession, term: str) -> Purchase | None:
    low = term.lower()
    stmt = select(Purchase).where(
        func.lower(func.coalesce(Purchase.reference_no, "")) == low
    )
    p = (await db.execute(stmt)).scalars().first()
    if p:
        return p
    stmt = select(Purchase).where(func.lower(Purchase.id) == low)
    p = (await db.execute(stmt)).scalars().first()
    if p:
        return p
    if len(term) >= 7:
        stmt = select(Purchase).where(func.lower(Purchase.id).startswith(low))
        p = (await db.execute(stmt)).scalars().first()
        if p:
            return p
    return None


async def find_sale(db: AsyncSession, term: str) -> Sale | None:
    low = term.lower()
    stmt = select(Sale).where(func.lower(Sale.id) == low)
    s = (await db.execute(stmt)).scalars().first()
    if s:
        return s
    if len(term) >= 7:
        stmt = select(Sale).where(func.lower(Sale.id).startswith(low))
        s = (await db.execute(stmt)).scalars().first()
        if s:
            return s
    return None


async def build_purchase_statement(db: AsyncSession, purchase_id: str) -> InvoiceLedgerOut:
    purchase = (await db.execute(
        select(Purchase)
        .options(
            selectinload(Purchase.supplier),
            selectinload(Purchase.lines).selectinload(PurchaseLine.variant),
        )
        .where(Purchase.id == purchase_id)
    )).scalars().first()
    if not purchase:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase invoice not found")

    total = sum((Decimal(str(l.line_total)) for l in purchase.lines), Decimal("0"))

    # Returns against this invoice (grouped by return document).
    pline_ids = [l.id for l in purchase.lines]
    returns: list[tuple] = []
    if pline_ids:
        rows = (await db.execute(
            select(PurchaseReturn, PurchaseReturnLine)
            .join(PurchaseReturnLine, PurchaseReturnLine.purchase_return_id == PurchaseReturn.id)
            .where(PurchaseReturnLine.purchase_line_id.in_(pline_ids))
        )).all()
        agg: dict[str, list] = defaultdict(list)
        for ret, line in rows:
            agg[ret.id].append((ret, line))
        for rid, group in agg.items():
            ret = group[0][0]
            rtotal = sum((Decimal(str(l.line_total)) for _, l in group), Decimal("0"))
            returns.append((ret.return_date, ret.id, rtotal, ret.reason))

    payments = (await db.execute(
        select(Payment).where(Payment.purchase_id == purchase.id)
    )).scalars().all()

    # Statement from your own books: the invoice debits (value received),
    # returns and outward payments credit it. Balance = what remains due.
    balance = Decimal("0")
    transactions: list[InvoiceLedgerTransaction] = []
    balance += total
    transactions.append(InvoiceLedgerTransaction(
        date=purchase.purchase_date,
        description="Purchase invoice",
        debit=total,
        credit=Decimal("0"),
        balance=balance,
    ))

    later: list[tuple] = []
    for rdate, rid, rtotal, reason in returns:
        later.append((
            rdate, 0,
            InvoiceLedgerTransaction(
                date=rdate,
                description=f"Purchase return{(' — ' + reason) if reason else ''} (#{rid[:8]})",
                debit=Decimal("0"),
                credit=rtotal,
                balance=Decimal("0"),
            ),
        ))
    for pymt in payments:
        if pymt.direction == PaymentDirection.PAID_TO_SUPPLIER:
            later.append((
                pymt.payment_date, 1,
                InvoiceLedgerTransaction(
                    date=pymt.payment_date,
                    description=f"Payment to supplier (#{pymt.id[:8]})",
                    debit=Decimal("0"),
                    credit=pymt.amount,
                    balance=Decimal("0"),
                ),
            ))
        elif pymt.direction == PaymentDirection.REFUND_FROM_SUPPLIER:
            later.append((
                pymt.payment_date, 2,
                InvoiceLedgerTransaction(
                    date=pymt.payment_date,
                    description=f"Refund received from supplier (#{pymt.id[:8]})",
                    debit=pymt.amount,
                    credit=Decimal("0"),
                    balance=Decimal("0"),
                ),
            ))
    later.sort(key=lambda t: (t[0], t[1]))
    transactions_out: list[InvoiceLedgerTransaction] = []
    running = Decimal("0")
    for tx in transactions:
        running = running + tx.debit - tx.credit
        transactions_out.append(InvoiceLedgerTransaction(
            date=tx.date, description=tx.description,
            debit=tx.debit, credit=tx.credit, balance=running,
        ))
    for _, _, tx in later:
        running = running + tx.debit - tx.credit
        transactions_out.append(InvoiceLedgerTransaction(
            date=tx.date, description=tx.description,
            debit=tx.debit, credit=tx.credit, balance=running,
        ))

    return InvoiceLedgerOut(
        kind="PURCHASE",
        id=purchase.id,
        reference_no=purchase.reference_no,
        invoice_date=purchase.purchase_date,
        status=purchase.status.value,
        party_id=purchase.supplier_id,
        party_name=purchase.supplier.name,
        party_type=purchase.supplier.party_type,
        total=total,
        amount_paid=purchase.amount_paid,
        returned_amount=purchase.returned_amount,
        outstanding=total - purchase.amount_paid - purchase.returned_amount,
        lines=[
            InvoiceLedgerLine(
                variant_name=l.variant.name if l.variant else None,
                variant_sku=l.variant.sku if l.variant else None,
                qty=l.qty,
                rate=l.unit_cost,
                line_total=l.line_total,
            )
            for l in purchase.lines
        ],
        transactions=transactions_out,
    )


async def build_sale_statement(db: AsyncSession, sale_id: str) -> InvoiceLedgerOut:
    sale = (await db.execute(
        select(Sale)
        .options(
            selectinload(Sale.party),
            selectinload(Sale.lines).selectinload(SaleLine.variant),
        )
        .where(Sale.id == sale_id)
    )).scalars().first()
    if not sale:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sale invoice not found")

    total = sum((Decimal(str(l.line_total)) for l in sale.lines), Decimal("0"))

    sline_ids = [l.id for l in sale.lines]
    returns: list[tuple] = []
    if sline_ids:
        rows = (await db.execute(
            select(SalesReturn, SalesReturnLine)
            .join(SalesReturnLine, SalesReturnLine.sales_return_id == SalesReturn.id)
            .where(SalesReturnLine.sale_line_id.in_(sline_ids))
        )).all()
        agg: dict[str, list] = defaultdict(list)
        for ret, line in rows:
            agg[ret.id].append((ret, line))
        for rid, group in agg.items():
            ret = group[0][0]
            rtotal = sum((Decimal(str(l.line_total)) for _, l in group), Decimal("0"))
            returns.append((ret.return_date, ret.id, rtotal, ret.reason))

    payments = (await db.execute(
        select(Payment).where(Payment.sale_id == sale.id)
    )).scalars().all()

    balance = Decimal("0")
    transactions: list[InvoiceLedgerTransaction] = []
    balance += total
    transactions.append(InvoiceLedgerTransaction(
        date=sale.sale_date,
        description="Sale invoice",
        debit=total,
        credit=Decimal("0"),
        balance=balance,
    ))

    later: list[tuple] = []
    for rdate, rid, rtotal, reason in returns:
        later.append((
            rdate, 0,
            InvoiceLedgerTransaction(
                date=rdate,
                description=f"Sales return{(' — ' + reason) if reason else ''} (#{rid[:8]})",
                debit=Decimal("0"),
                credit=rtotal,
                balance=Decimal("0"),
            ),
        ))
    for pymt in payments:
        if pymt.direction == PaymentDirection.RECEIVED_FROM_CUSTOMER:
            later.append((
                pymt.payment_date, 1,
                InvoiceLedgerTransaction(
                    date=pymt.payment_date,
                    description=f"Payment received from customer (#{pymt.id[:8]})",
                    debit=Decimal("0"),
                    credit=pymt.amount,
                    balance=Decimal("0"),
                ),
            ))
        elif pymt.direction == PaymentDirection.REFUND_TO_CUSTOMER:
            later.append((
                pymt.payment_date, 2,
                InvoiceLedgerTransaction(
                    date=pymt.payment_date,
                    description=f"Refund to customer (#{pymt.id[:8]})",
                    debit=pymt.amount,
                    credit=Decimal("0"),
                    balance=Decimal("0"),
                ),
            ))
    later.sort(key=lambda t: (t[0], t[1]))

    transactions_out: list[InvoiceLedgerTransaction] = []
    running = Decimal("0")
    for tx in transactions:
        running = running + tx.debit - tx.credit
        transactions_out.append(InvoiceLedgerTransaction(
            date=tx.date, description=tx.description,
            debit=tx.debit, credit=tx.credit, balance=running,
        ))
    for _, _, tx in later:
        running = running + tx.debit - tx.credit
        transactions_out.append(InvoiceLedgerTransaction(
            date=tx.date, description=tx.description,
            debit=tx.debit, credit=tx.credit, balance=running,
        ))

    return InvoiceLedgerOut(
        kind="SALE",
        id=sale.id,
        reference_no=None,
        invoice_date=sale.sale_date,
        status=sale.status.value,
        party_id=sale.party_id,
        party_name=sale.party.name if sale.party else None,
        party_type=sale.party.party_type if sale.party else None,
        total=total,
        amount_paid=sale.amount_paid,
        returned_amount=sale.returned_amount,
        outstanding=total - sale.amount_paid - sale.returned_amount,
        lines=[
            InvoiceLedgerLine(
                variant_name=l.variant.name if l.variant else None,
                variant_sku=l.variant.sku if l.variant else None,
                qty=l.qty,
                rate=l.unit_price,
                line_total=l.line_total,
            )
            for l in sale.lines
        ],
        transactions=transactions_out,
    )


@router.get("", response_model=Union[InvoiceLedgerOut, InvoiceLedgerPartyOut])
async def get_invoice_ledger(
    invoice_number: str = Query(..., description="Invoice reference/id or a party id"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    term = invoice_number.strip().lstrip("#").strip()
    if not term:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invoice or party number is required")

    purchase = await find_purchase(db, term)
    if purchase:
        return await build_purchase_statement(db, purchase.id)

    sale = await find_sale(db, term)
    if sale:
        return await build_sale_statement(db, sale.id)

    # A plain number with no invoice match -> treat it as a party id and
    # list that customer/supplier's invoices (invoice-wise ledger).
    if term.isdigit():
        party = await db.get(Party, int(term))
        if party:
            return await build_party_statement(db, party)

    raise HTTPException(
        status.HTTP_404_NOT_FOUND,
        "No purchase/sale invoice or customer/supplier id matches that number",
    )


async def build_party_statement(db: AsyncSession, party: Party) -> InvoiceLedgerPartyOut:
    invoices: list[InvoiceLedgerPartyInvoice] = []
    if party.party_type == "SUPPLIER":
        rows = (await db.execute(
            select(Purchase)
            .options(selectinload(Purchase.lines))
            .where(
                Purchase.supplier_id == party.id,
                Purchase.status == PurchaseStatus.RECEIVED,
            )
        )).scalars().all()
        for p in rows:
            total = sum((Decimal(str(l.line_total)) for l in p.lines), Decimal("0"))
            invoices.append(InvoiceLedgerPartyInvoice(
                invoice_kind="PURCHASE",
                id=p.id,
                reference_no=p.reference_no,
                invoice_date=p.purchase_date,
                status=p.status.value,
                total=total,
                amount_paid=p.amount_paid,
                returned_amount=p.returned_amount,
                outstanding=total - p.amount_paid - p.returned_amount,
            ))
    else:
        rows = (await db.execute(
            select(Sale)
            .options(selectinload(Sale.lines))
            .where(Sale.party_id == party.id, Sale.status == SaleStatus.COMPLETED)
        )).scalars().all()
        for s in rows:
            total = sum((Decimal(str(l.line_total)) for l in s.lines), Decimal("0"))
            invoices.append(InvoiceLedgerPartyInvoice(
                invoice_kind="SALE",
                id=s.id,
                reference_no=None,
                invoice_date=s.sale_date,
                status=s.status.value,
                total=total,
                amount_paid=s.amount_paid,
                returned_amount=s.returned_amount,
                outstanding=total - s.amount_paid - s.returned_amount,
            ))

    invoices.sort(key=lambda i: i.invoice_date, reverse=True)
    return InvoiceLedgerPartyOut(
        party_id=party.id,
        party_name=party.name,
        party_type=party.party_type,
        invoices=invoices,
    )