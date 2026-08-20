from datetime import date
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from app.db import get_db
from app.models import Party as PartyModel
from app.models.party_ledger_entry import PartyLedgerEntry
from app.models.enums import PartyType, LedgerRefType
from app.schemas.party import (
    PartyCreate, PartyOut, PartyUpdate, PartyOutPaginate, PartyBalanceOut,
)
from app.schemas.party_ledger_entry import PartyLedgerEntryOutPaginate
from app.api.deps import require_superadmin_or_admin, get_current_user
from decimal import Decimal

router = APIRouter(prefix="/party", tags=["party"])


@router.post("", response_model=PartyOut, status_code=status.HTTP_201_CREATED)
async def create_party(
    party: PartyCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin),
):
    try:
        data = party.model_dump()
        data.setdefault("balance_cached", Decimal("0"))
        data.setdefault("credit_limit", Decimal("0"))

        new_party = PartyModel(**data)
        db.add(new_party)
        await db.commit()
        await db.refresh(new_party)
        return new_party
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Party with this identifier already exists",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/", response_model=PartyOutPaginate)
async def list_parties(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(
        10, ge=1, le=200, description="Max number of items to return"),
    is_active: bool | None = Query(
        None, description="Filter by active status"),
    party_type: PartyType | None = Query(
        None, description="Filter by party type"),
    search: str | None = Query(
        None, description="Search by name, phone, or email"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(PartyModel)
    count_stmt = select(func.count()).select_from(PartyModel)

    if is_active is not None:
        stmt = stmt.where(PartyModel.is_active == is_active)
        count_stmt = count_stmt.where(PartyModel.is_active == is_active)

    if party_type is not None:
        stmt = stmt.where(PartyModel.party_type == party_type)
        count_stmt = count_stmt.where(PartyModel.party_type == party_type)

    if search:
        term = f"%{search}%"
        search_filter = or_(
            PartyModel.name.ilike(term),
            PartyModel.phone.ilike(term),
            PartyModel.email.ilike(term),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return PartyOutPaginate(
        total=total,
        page=(skip // limit) + 1,
        size=len(items),
        items=items,
    )


@router.get("/dues", response_model=PartyOutPaginate)
async def list_party_dues(
    party_type: PartyType = Query(
        ..., description="SUPPLIER = who you owe, CUSTOMER = who owes you"
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Parties with a non-zero balance, sorted by amount outstanding.

    Convention: balance_cached is always "amount currently outstanding in
    the direction natural to that party_type" - positive for SUPPLIER
    means you owe them, positive for CUSTOMER means they owe you. See
    app/services/party_ledger.py for exactly how this is maintained.
    """
    stmt = (
        select(PartyModel)
        .where(PartyModel.party_type == party_type)
        .where(PartyModel.balance_cached != 0)
        .order_by(PartyModel.balance_cached.desc())
    )
    count_stmt = (
        select(func.count())
        .select_from(PartyModel)
        .where(PartyModel.party_type == party_type)
        .where(PartyModel.balance_cached != 0)
    )

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return PartyOutPaginate(
        total=total,
        page=(skip // limit) + 1,
        size=len(items),
        items=items,
    )


@router.get("/{id}", response_model=PartyOut)
async def get_party(
    id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    party = await db.execute(select(PartyModel).where(PartyModel.id == id))
    party = party.scalars().first()

    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Party not found"
        )
    return party


@router.get("/{id}/balance", response_model=PartyBalanceOut)
async def get_party_balance(
    id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(PartyModel).where(PartyModel.id == id))
    party = result.scalars().first()

    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Party not found"
        )

    # NOTE: this reads the cached value for speed. If you ever suspect drift
    # (e.g. after a manual DB fix or a bug), recompute from
    # SUM(credit - debit) over party_ledger_entry instead, via a
    # reconciliation utility - never patch balance_cached by hand.
    available_credit = party.credit_limit - party.balance_cached

    return PartyBalanceOut(
        id=party.id,
        name=party.name,
        party_type=party.party_type,
        balance_cached=party.balance_cached,
        credit_limit=party.credit_limit,
        available_credit=available_credit,
    )


@router.get("/{id}/ledger", response_model=PartyLedgerEntryOutPaginate)
async def get_party_ledger(
    id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    ref_type: LedgerRefType | None = Query(None),
    from_date: date | None = Query(None),
    to_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Was a TODO - now that PartyLedgerEntry exists, implemented here as a
    convenience alias for GET /party-ledger/{party_id} (same query logic,
    kept in sync with app/api/party_ledger_entry.py).
    """
    party_result = await db.execute(select(PartyModel).where(PartyModel.id == id))
    if not party_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Party not found")

    stmt = select(PartyLedgerEntry).where(PartyLedgerEntry.party_id == id)
    count_stmt = (
        select(func.count()).select_from(PartyLedgerEntry).where(
            PartyLedgerEntry.party_id == id)
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
    stmt = stmt.order_by(PartyLedgerEntry.entry_date.asc()
                         ).offset(skip).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    return PartyLedgerEntryOutPaginate(total=total, page=(skip // limit) + 1, size=len(items), items=items)


@router.put("/{id}", response_model=PartyOut)
async def update_party(
    id: int,
    party_update: PartyUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin),
):
    try:
        result = await db.execute(select(PartyModel).where(PartyModel.id == id))
        party = result.scalars().first()

        if not party:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Party not found"
            )

        update_data = party_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(party, key, value)

        await db.commit()
        await db.refresh(party)
        return party
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.patch("/{id}/deactivate", response_model=PartyOut)
async def deactivate_party(
    id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin),
):
    result = await db.execute(select(PartyModel).where(PartyModel.id == id))
    party = result.scalars().first()

    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Party not found"
        )

    party.is_active = False
    await db.commit()
    await db.refresh(party)
    return party


@router.patch("/{id}/activate", response_model=PartyOut)
async def activate_party(
    id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin),
):
    result = await db.execute(select(PartyModel).where(PartyModel.id == id))
    party = result.scalars().first()

    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Party not found"
        )

    party.is_active = True
    await db.commit()
    await db.refresh(party)
    return party
