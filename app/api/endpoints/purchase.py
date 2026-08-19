from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.api.deps import require_superadmin_or_admin_or_storekeeper, get_current_user
from app.db import get_db
from app.models.purchase import Purchase, PurchaseLine
from app.models.party import Party
from app.models.product_variant import ProductVariant
from app.models.enums import PartyType, PurchaseStatus
from app.models.user import User
from app.schemas.purchase import (
    PurchaseCreate, PurchaseUpdate, PurchaseOut, PurchaseOutPaginate,
    PurchaseReceive, PurchaseCancel,
)
from app.services.purchase import receive_purchase as svc_receive_purchase

router = APIRouter(prefix="/purchases", tags=["purchase"])


# ─── helpers ────────────────────────────────────────────────────────────────

async def _get_purchase_or_404(
    db: AsyncSession, purchase_id: str, *, load_lines: bool = True
) -> Purchase:
    stmt = select(Purchase).where(Purchase.id == purchase_id)
    if load_lines:
        stmt = stmt.options(selectinload(Purchase.lines))
    result = await db.execute(stmt)
    purchase = result.scalars().first()
    if not purchase:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase not found")
    return purchase


async def _assert_supplier(db: AsyncSession, supplier_id: int) -> Party:
    result = await db.execute(select(Party).where(Party.id == supplier_id))
    party = result.scalars().first()
    if not party:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    if party.party_type != PartyType.SUPPLIER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "party_id must belong to a SUPPLIER")
    return party


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


# ─── CREATE ─────────────────────────────────────────────────────────────────

@router.post("", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
async def create_purchase(
    payload: PurchaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_or_admin_or_storekeeper),
):
    await _assert_supplier(db, payload.supplier_id)
    await _assert_variants_exist(db, [line.variant_id for line in payload.lines])

    try:
        purchase = Purchase(
            supplier_id=payload.supplier_id,
            purchase_date=payload.purchase_date,
            reference_no=payload.reference_no,
            notes=payload.notes,
            status=PurchaseStatus.DRAFT,
            created_by=current_user.id,
        )
        for line_data in payload.lines:
            purchase.lines.append(PurchaseLine(
                variant_id=line_data.variant_id,
                qty=line_data.qty,
                unit_cost=line_data.unit_cost,
                # line_total is NOT NULL on PurchaseLine - must be set here,
                # the original version of this router omitted it entirely.
                line_total=line_data.qty * line_data.unit_cost,
            ))

        db.add(purchase)
        await db.commit()
        await db.refresh(purchase, attribute_names=["lines"])
        return purchase
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Integrity error while creating purchase")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


# ─── LIST ───────────────────────────────────────────────────────────────────

@router.get("", response_model=PurchaseOutPaginate)
async def list_purchases(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    supplier_id: int | None = Query(None),
    # Renamed from `status` to avoid shadowing the `status` module imported
    # above (the alias keeps the query string itself unchanged: ?status=).
    purchase_status: PurchaseStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(Purchase).options(selectinload(Purchase.lines))
    count_stmt = select(func.count()).select_from(Purchase)

    if supplier_id is not None:
        stmt = stmt.where(Purchase.supplier_id == supplier_id)
        count_stmt = count_stmt.where(Purchase.supplier_id == supplier_id)
    if purchase_status is not None:
        stmt = stmt.where(Purchase.status == purchase_status)
        count_stmt = count_stmt.where(Purchase.status == purchase_status)

    total = (await db.execute(count_stmt)).scalar_one()
    stmt = stmt.order_by(Purchase.purchase_date.desc(), Purchase.created_at.desc())
    stmt = stmt.offset(skip).limit(limit)
    items = (await db.execute(stmt)).scalars().all()

    return PurchaseOutPaginate(total=total, page=(skip // limit) + 1, size=len(items), items=items)


# ─── GET ONE ────────────────────────────────────────────────────────────────

@router.get("/{id}", response_model=PurchaseOut)
async def get_purchase(id: str, db: AsyncSession = Depends(get_db), _=Depends(get_current_user)):
    return await _get_purchase_or_404(db, id)


# ─── UPDATE (DRAFT only) ────────────────────────────────────────────────────

@router.put("/{id}", response_model=PurchaseOut)
async def update_purchase(
    id: str,
    payload: PurchaseUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    purchase = await _get_purchase_or_404(db, id)
    if purchase.status != PurchaseStatus.DRAFT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only DRAFT purchases can be updated")

    update_data = payload.model_dump(exclude_unset=True)
    if "supplier_id" in update_data:
        await _assert_supplier(db, update_data["supplier_id"])

    try:
        for field, value in update_data.items():
            setattr(purchase, field, value)
        await db.commit()
        await db.refresh(purchase, attribute_names=["lines"])
        return purchase
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Integrity error while updating purchase")
    except Exception as e:
        await db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


# ─── RECEIVE (DRAFT → RECEIVED) ─────────────────────────────────────────────

@router.post("/{id}/receive", response_model=PurchaseOut)
async def receive_purchase(
    id: str,
    payload: PurchaseReceive,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_or_admin_or_storekeeper),
):
    """
    Creates one ProductBatch + one StockMovement(PURCHASE_IN) per line,
    plus one PartyLedgerEntry for the whole purchase - see
    app/services/purchase.py::receive_purchase for the actual logic. This
    endpoint now calls the real service instead of just flipping status.
    """
    purchase = await _get_purchase_or_404(db, id)

    if purchase.status != PurchaseStatus.DRAFT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot receive a purchase that is already {purchase.status}",
        )
    if not purchase.lines:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Purchase has no lines - nothing to receive")

    try:
        purchase = await svc_receive_purchase(db, purchase, performed_by=current_user.id)
        await db.commit()
        await db.refresh(purchase, attribute_names=["lines"])
        return purchase
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e))


# ─── CANCEL (DRAFT → CANCELLED) ─────────────────────────────────────────────

@router.post("/{id}/cancel", response_model=PurchaseOut)
async def cancel_purchase(
    id: str,
    payload: PurchaseCancel,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    purchase = await _get_purchase_or_404(db, id)
    if purchase.status != PurchaseStatus.DRAFT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot cancel a purchase that is already {purchase.status}",
        )

    purchase.status = PurchaseStatus.CANCELLED
    if payload.reason:
        purchase.notes = ((purchase.notes or "") + f"\n[CANCELLED] {payload.reason}").strip()

    await db.commit()
    await db.refresh(purchase, attribute_names=["lines"])
    return purchase
