from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.models.payment import Payment
from app.models.party import Party
from app.models.sale import Sale
from app.models.purchase import Purchase
from app.models.enums import PaymentDirection, LedgerRefType, SaleStatus, PurchaseStatus
from app.services.party_ledger import write_ledger_entry


async def record_payment(db, payload, created_by: int | None) -> Payment:
    """
    Does not commit - the router commits once, after this returns.

    If party_id is set, writes exactly one PartyLedgerEntry alongside the
    Payment. If party_id is None, the Payment is a standalone walk-in
    event with no ledger entry.

    sale_id (RECEIVED_FROM_CUSTOMER / REFUND_TO_CUSTOMER only): applies
    the payment to a specific COMPLETED sale ORDER, so each order tracks its
    own balance (SUM(line_total) - amount_paid - returned_amount) rather
    than everything folding into the party's overall balance. When set:
      - validates the sale is COMPLETED and belongs to the same party;
      - RECEIVED_FROM_CUSTOMER: rejects overpayment (amount > outstanding)
        and increments sale.amount_paid;
      - REFUND_TO_CUSTOMER: refunds an order's credit — rejects amounts
        beyond that credit (and beyond what was actually paid on the
        order) and decrements sale.amount_paid, so outstanding returns to 0.

    Direction -> debit/credit mapping (fed into write_ledger_entry, which
    then applies the party-type-dependent sign - see
    app/services/party_ledger.py for why supplier/customer aren't
    symmetric):
      PAID_TO_SUPPLIER       -> debit  (reduces what you owe them)
      RECEIVED_FROM_CUSTOMER -> credit (reduces what they owe you)
      REFUND_FROM_SUPPLIER   -> credit (they pay off what they owed you)
      REFUND_TO_CUSTOMER     -> debit  (you pay off what you owed them)
    """
    payment = Payment(
        party_id=payload.party_id,
        direction=payload.direction,
        amount=payload.amount,
        method=payload.method,
        payment_date=payload.payment_date,
        reference_no=payload.reference_no,
        notes=payload.notes,
        sales_return_id=payload.sales_return_id,
        sale_id=payload.sale_id,
        purchase_id=payload.purchase_id,
        created_by=created_by,
    )
    db.add(payment)
    await db.flush()

    if payload.sale_id is not None:
        if payload.direction not in (
            PaymentDirection.RECEIVED_FROM_CUSTOMER,
            PaymentDirection.REFUND_TO_CUSTOMER,
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "sale_id can only be used with RECEIVED_FROM_CUSTOMER or REFUND_TO_CUSTOMER payments",
            )
        if payload.party_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "party_id is required when allocating a payment to a sale",
            )
        sale = (await db.execute(
            select(Sale)
            .options(selectinload(Sale.lines))
            .where(Sale.id == payload.sale_id)
        )).scalars().first()
        if not sale or sale.status != SaleStatus.COMPLETED:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Sale not found or not completed",
            )
        if sale.party_id != payload.party_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "This sale belongs to a different party",
            )
        sale_total = sum((Decimal(str(l.line_total)) for l in sale.lines), Decimal("0"))
        outstanding = sale_total - sale.amount_paid - sale.returned_amount

        if payload.direction == PaymentDirection.RECEIVED_FROM_CUSTOMER:
            if payload.amount > outstanding:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Payment exceeds the sale's outstanding balance ({outstanding})",
                )
            sale.amount_paid = sale.amount_paid + payload.amount
        else:  # REFUND_TO_CUSTOMER - repay an order's credit
            credit = -outstanding if outstanding < 0 else Decimal("0")
            if payload.amount > credit:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Refund exceeds the order's credit ({credit})",
                )
            if payload.amount > sale.amount_paid:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Refund exceeds the amount paid on this order ({sale.amount_paid})",
                )
            sale.amount_paid = sale.amount_paid - payload.amount

    if payload.purchase_id is not None:
        if payload.direction not in (
            PaymentDirection.PAID_TO_SUPPLIER,
            PaymentDirection.REFUND_FROM_SUPPLIER,
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "purchase_id can only be used with PAID_TO_SUPPLIER or REFUND_FROM_SUPPLIER payments",
            )
        if payload.party_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "party_id is required when allocating a payment to a purchase",
            )
        purchase = (await db.execute(
            select(Purchase)
            .options(selectinload(Purchase.lines))
            .where(Purchase.id == payload.purchase_id)
        )).scalars().first()
        if not purchase or purchase.status != PurchaseStatus.RECEIVED:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Purchase not found or not received",
            )
        if purchase.supplier_id != payload.party_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "This purchase belongs to a different supplier",
            )
        purchase_total = sum((Decimal(str(l.line_total)) for l in purchase.lines), Decimal("0"))
        outstanding = purchase_total - purchase.amount_paid - purchase.returned_amount

        if payload.direction == PaymentDirection.PAID_TO_SUPPLIER:
            if payload.amount > outstanding:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Payment exceeds the purchase's outstanding balance ({outstanding})",
                )
            purchase.amount_paid = purchase.amount_paid + payload.amount
        else:  # REFUND_FROM_SUPPLIER - collect an invoice's credit
            credit = -outstanding if outstanding < 0 else Decimal("0")
            if payload.amount > credit:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Refund exceeds the invoice's credit ({credit})",
                )
            if payload.amount > purchase.amount_paid:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    f"Refund exceeds the amount paid on this invoice ({purchase.amount_paid})",
                )
            purchase.amount_paid = purchase.amount_paid - payload.amount

    if payload.party_id is not None:
        party = await db.get(Party, payload.party_id)

        notes = None
        if payload.sale_id is not None:
            notes = f"Payment {payment.id} for sale {payload.sale_id}"
        if payload.purchase_id is not None:
            notes = f"Payment {payment.id} for purchase {payload.purchase_id}"

        debit_directions = {PaymentDirection.PAID_TO_SUPPLIER, PaymentDirection.REFUND_TO_CUSTOMER}
        if payload.direction in debit_directions:
            write_ledger_entry(
                db, party, LedgerRefType.PAYMENT, payment.id, debit=payload.amount,
                notes=notes,
            )
        else:  # RECEIVED_FROM_CUSTOMER, REFUND_FROM_SUPPLIER
            write_ledger_entry(
                db, party, LedgerRefType.PAYMENT, payment.id, credit=payload.amount,
                notes=notes,
            )

    return payment
