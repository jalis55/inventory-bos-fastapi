from app.models.payment import Payment
from app.models.party import Party
from app.models.enums import PaymentDirection, LedgerRefType
from app.services.party_ledger import write_ledger_entry


async def record_payment(db, payload, created_by: int | None) -> Payment:
    """
    Does not commit - the router commits once, after this returns.

    If party_id is set, writes exactly one PartyLedgerEntry alongside the
    Payment. If party_id is None, the Payment is a standalone walk-in
    event with no ledger entry.

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
        created_by=created_by,
    )
    db.add(payment)
    await db.flush()

    if payload.party_id is not None:
        party = await db.get(Party, payload.party_id)

        debit_directions = {PaymentDirection.PAID_TO_SUPPLIER, PaymentDirection.REFUND_TO_CUSTOMER}
        if payload.direction in debit_directions:
            write_ledger_entry(
                db, party, LedgerRefType.PAYMENT, payment.id, debit=payload.amount
            )
        else:  # RECEIVED_FROM_CUSTOMER, REFUND_FROM_SUPPLIER
            write_ledger_entry(
                db, party, LedgerRefType.PAYMENT, payment.id, credit=payload.amount
            )

    return payment
