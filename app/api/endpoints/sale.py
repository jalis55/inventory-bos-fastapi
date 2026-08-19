from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import require_superadmin_or_admin_or_storekeeper, get_current_user
from app.db import get_db
from app.models.sale import Sale, SaleLine
from app.models.party import Party
from app.models.product_variant import ProductVariant
from app.models.enums import PartyType, SaleStatus
from app.models.user import User
from app.schemas.sale import (
    SaleCreate, SaleUpdate, SaleOut, SaleOutPaginate, SaleComplete, SaleCancel,
)
from app.services.sale import complete_sale as svc_complete_sale

router = APIRouter(prefix="/sales", tags=["sale"])


# ─── helpers ────────────────────────────────────────────────────────────────

async def _get_sale_or_404(db: AsyncSession, sale_id: str, *, load_lines: bool = True) -> Sale:
    stmt = select(Sale).where(Sale.id == sale_id)
    if load_lines:
        stmt = stmt.options(selectinload(Sale.lines))
    result = await db.execute(stmt)
    sale = result.scalars().first()
    if not sale:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sale not found")
    return sale


async def _assert_customer_or_none(db: AsyncSession, party_id: int | None) -> None:
    if party_id is None:
        return  # walk-in is allowed
    result = await db.execute(select(Party).where(Party.id == party_id))
    party = result.scalars().first()
    if not party:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    if party.party_type not in (PartyType.CUSTOMER, PartyType.WALK_IN):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "party_id must belong to a CUSTOMER or WALK_IN")


async def _assert_variants_exist(db: AsyncSession, variant_ids: list[str]) -> None:
    if not variant_ids:
        return
    result = await db.execute(select(ProductVariant.id).where(ProductVariant.id.in_(variant_ids)))
    found = {row[0] for row in result.all()}
    missing = set(variant_ids) - found
    if missing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"Variant(s) not found: {', '.join(missing)}"
        )


# ─── CREATE (DRAFT) ─────────────────────────────────────────────────────────

@router.post("", response_model=SaleOut, status_code=status.HTTP_201_CREATED)
async def create_sale(
    payload: SaleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_or_admin_or_storekeeper),
):
    """
    Creates a DRAFT sale. batch_id and unit_cost_snapshot are left NULL on
    every line (they're nullable on SaleLine specifically for this) until
    complete_sale() FIFO-allocates real batches - see
    app/services/sale.py. The earlier "pending"/0 placeholder values are
    gone; there's no longer a NOT NULL constraint forcing them.
    line_total IS set now, since qty * unit_price doesn't depend on which
    batch ends up supplying the stock.
    """
    await _assert_customer_or_none(db, payload.party_id)
    await _assert_variants_exist(db, [line.variant_id for line in payload.lines])

    try:
        sale = Sale(
            party_id=payload.party_id,
            sale_date=payload.sale_date,
            status=SaleStatus.DRAFT,
            created_by=current_user.id,
        )
        for line_data in payload.lines:
            sale.lines.append(SaleLine(
                variant_id=line_data.variant_id,
                qty=line_data.qty,
                unit_price=line_data.unit_price,
                line_total=line_data.qty * line_data.unit_price,
                # batch_id / unit_cost_snapshot intentionally left NULL
            ))

        db.add(sale)
        await db.commit()
        await db.refresh(sale, attribute_names=["lines"])
        return sale
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Integrity error while creating sale")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


# ─── LIST ───────────────────────────────────────────────────────────────────

@router.get("", response_model=SaleOutPaginate)
async def list_sales(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    party_id: int | None = Query(None),
    sale_status: SaleStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(Sale).options(selectinload(Sale.lines))
    count_stmt = select(func.count()).select_from(Sale)

    if party_id is not None:
        stmt = stmt.where(Sale.party_id == party_id)
        count_stmt = count_stmt.where(Sale.party_id == party_id)
    if sale_status is not None:
        stmt = stmt.where(Sale.status == sale_status)
        count_stmt = count_stmt.where(Sale.status == sale_status)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Sale.sale_date.desc(), Sale.created_at.desc())
    stmt = stmt.offset(skip).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    return SaleOutPaginate(total=total, page=(skip // limit) + 1, size=len(items), items=items)


# ─── GET ONE ────────────────────────────────────────────────────────────────

@router.get("/{id}", response_model=SaleOut)
async def get_sale(id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    return await _get_sale_or_404(db, id)


# ─── UPDATE (DRAFT only) ────────────────────────────────────────────────────

@router.put("/{id}", response_model=SaleOut)
async def update_sale(
    id: str,
    payload: SaleUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    sale = await _get_sale_or_404(db, id)
    if sale.status != SaleStatus.DRAFT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only DRAFT sales can be updated")

    update_data = payload.model_dump(exclude_unset=True)
    if "party_id" in update_data:
        await _assert_customer_or_none(db, update_data["party_id"])

    try:
        for field, value in update_data.items():
            setattr(sale, field, value)
        await db.commit()
        await db.refresh(sale, attribute_names=["lines"])
        return sale
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Integrity error while updating sale")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


# ─── COMPLETE (DRAFT → COMPLETED) ───────────────────────────────────────────

@router.post("/{id}/complete", response_model=SaleOut)
async def complete_sale(
    id: str,
    payload: SaleComplete,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_or_admin_or_storekeeper),
):
    """
    FIFO-allocates batches, decrements stock via record_batch_movement(),
    writes StockMovement per batch touched, and (if the sale has a party)
    one PartyLedgerEntry - see app/services/sale.py::complete_sale. This
    endpoint now calls the real service instead of just flipping status.
    """
    sale = await _get_sale_or_404(db, id)

    if sale.status != SaleStatus.DRAFT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Cannot complete a sale that is already {sale.status}"
        )
    if not sale.lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Sale has no lines - nothing to complete")

    try:
        sale = await svc_complete_sale(db, sale, performed_by=current_user.id)
        await db.commit()
        await db.refresh(sale, attribute_names=["lines"])
        return sale
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


# ─── CANCEL (DRAFT → CANCELLED) ─────────────────────────────────────────────

@router.post("/{id}/cancel", response_model=SaleOut)
async def cancel_sale(
    id: str,
    payload: SaleCancel,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    sale = await _get_sale_or_404(db, id)
    if sale.status != SaleStatus.DRAFT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Cannot cancel a sale that is already {sale.status}"
        )

    sale.status = SaleStatus.CANCELLED
    await db.commit()
    await db.refresh(sale, attribute_names=["lines"])
    return sale
