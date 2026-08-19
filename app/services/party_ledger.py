from decimal import Decimal
from typing import Optional
from app.models.party import Party
from app.models.party_ledger_entry import PartyLedgerEntry
from app.models.enums import LedgerRefType, PartyType


def write_ledger_entry(
    db,
    party: Party,
    ref_type: LedgerRefType,
    ref_id: str,
    debit: Decimal = Decimal("0"),
    credit: Decimal = Decimal("0"),
    notes: Optional[str] = None,
) -> PartyLedgerEntry:
    """
    The ONLY sanctioned way to write a party_ledger_entry or move
    party.balance_cached. Does not commit - the caller bundles this into
    the same transaction as the business event that caused it (purchase
    received, sale completed, return processed, payment recorded).

    debit/credit follow the standard payable-vs-receivable convention,
    which is NOT symmetric between party types - this is the one place
    that asymmetry is handled, so no other code should compute a balance
    delta by hand:

      - SUPPLIER (payable): credit increases what you owe them,
        debit decreases it.       balance_cached += (credit - debit)
      - CUSTOMER / WALK_IN (receivable): debit increases what they owe
        you, credit decreases it. balance_cached += (debit - credit)

    In both cases balance_cached ends up meaning "amount currently
    outstanding, in the direction natural to that party_type" - positive
    always means money is owed in that direction.
    """
    if party.party_type == PartyType.SUPPLIER:
        delta = credit - debit
    else:  # CUSTOMER or WALK_IN
        delta = debit - credit

    party.balance_cached = party.balance_cached + delta

    entry = PartyLedgerEntry(
        party_id=party.id,
        ref_type=ref_type,
        ref_id=ref_id,
        debit=debit,
        credit=credit,
        balance_after=party.balance_cached,
        notes=notes,
    )
    db.add(entry)
    return entry
