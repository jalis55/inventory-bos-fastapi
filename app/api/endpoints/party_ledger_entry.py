from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_current_user
from app.db import get_db
from app.models.party_ledger_entry import PartyLedgerEntry
from app.models.enums import LedgerRefType
from app.schemas.party_ledger_entry import PartyLedgerEntryOutPaginate

router = APIRouter(prefix="/party-ledger", tags=["party-ledger"])


@router.get("/{party_id}", response_model=PartyLedgerEntryOutPaginate)
async def get_party_ledger(
    party_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    ref_type: LedgerRefType | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    A party's account statement, oldest first (so balance_after reads as
    a running total top to bottom). This is the endpoint flagged as a
    TODO in the party router - now implemented.

    Read-only, same as stock_movements - there is no create/update/delete
    here. Every row is written exclusively by write_ledger_entry() in
    app/services/party_ledger.py, called from inside receive_purchase,
    complete_sale, the two return services, and record_payment.
    """
    stmt = select(PartyLedgerEntry).where(PartyLedgerEntry.party_id == party_id)
    count_stmt = (
        select(func.count()).select_from(PartyLedgerEntry).where(PartyLedgerEntry.party_id == party_id)
    )

    if ref_type is not None:
        stmt = stmt.where(PartyLedgerEntry.ref_type == ref_type)
        count_stmt = count_stmt.where(PartyLedgerEntry.ref_type == ref_type)
    if from_date is not None:
        stmt = stmt.where(PartyLedgerEntry.entry_date >= from_date)
        count_stmt = count_stmt.where(PartyLedgerEntry.entry_date >= from_date)
    if to_date is not None:
        stmt = stmt.where(PartyLedgerEntry.entry_date <= to_date)
        count_stmt = count_stmt.where(PartyLedgerEntry.entry_date <= to_date)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(PartyLedgerEntry.entry_date.asc()).offset(skip).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    return PartyLedgerEntryOutPaginate(total=total, page=(skip // limit) + 1, size=len(items), items=items)
