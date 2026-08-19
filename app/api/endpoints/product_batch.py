from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func
from app.api.deps import require_superadmin_or_admin_or_storekeeper, get_current_user
from app.models.product_batch import ProductBatch
from app.models.product_variant import ProductVariant
from app.schemas.product_batch import (
    ProductBatchCreate,
    ProductBatchExpiryUpdate,
    ProductBatchOut,
    ProductBatchOutPaginate,
)
from app.db import get_db

router = APIRouter(prefix="/batches", tags=["product-batch"])


@router.post(
    "",
    response_model=ProductBatchOut,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_batch(
    batch: ProductBatchCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    """
    Hidden from the public API docs (include_in_schema=False) on purpose.

    Once Purchase/PurchaseLine exist, batches should be created
    exclusively by the purchase-receiving flow - one call per PurchaseLine
    when a Purchase is marked RECEIVED - never by a general "create a
    batch" endpoint a client could call directly and desync stock from
    actual purchase history.

    Left callable here only so it's testable before the Purchase system
    is built. Once that exists, prefer moving this logic into the
    purchase-receiving service and removing this route entirely rather
    than leaving two ways to create the same thing.
    """
    variant_result = await db.execute(
        select(ProductVariant).where(ProductVariant.id == batch.variant_id)
    )
    if not variant_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found"
        )

    try:
        data = batch.model_dump()
        new_batch = ProductBatch(**data, qty_remaining=data["qty_received"])
        db.add(new_batch)
        await db.commit()
        await db.refresh(new_batch)
        return new_batch
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A batch already exists for this purchase_line_id (one batch per purchase line only)",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("", response_model=ProductBatchOutPaginate)
async def list_batches(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    variant_id: str | None = Query(None),
    supplier_id: int | None = Query(None),
    has_stock: bool | None = Query(
        None, description="True = qty_remaining > 0 only, False = fully consumed only"
    ),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(ProductBatch)
    count_stmt = select(func.count()).select_from(ProductBatch)

    if variant_id is not None:
        stmt = stmt.where(ProductBatch.variant_id == variant_id)
        count_stmt = count_stmt.where(ProductBatch.variant_id == variant_id)

    if supplier_id is not None:
        stmt = stmt.where(ProductBatch.supplier_id == supplier_id)
        count_stmt = count_stmt.where(ProductBatch.supplier_id == supplier_id)

    if has_stock is True:
        stmt = stmt.where(ProductBatch.qty_remaining > 0)
        count_stmt = count_stmt.where(ProductBatch.qty_remaining > 0)
    elif has_stock is False:
        stmt = stmt.where(ProductBatch.qty_remaining == 0)
        count_stmt = count_stmt.where(ProductBatch.qty_remaining == 0)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return ProductBatchOutPaginate(
        total=total, page=(skip // limit) + 1, size=len(items), items=items
    )


@router.get("/variant/{variant_id}/fifo", response_model=list[ProductBatchOut])
async def list_batches_fifo(
    variant_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Batches with remaining stock for a variant, oldest received_date
    first - the exact consumption order a FIFO sale should draw from.
    """
    result = await db.execute(
        select(ProductBatch)
        .where(ProductBatch.variant_id == variant_id, ProductBatch.qty_remaining > 0)
        .order_by(ProductBatch.received_date.asc(), ProductBatch.created_at.asc())
    )
    return result.scalars().all()


@router.get("/{id}", response_model=ProductBatchOut)
async def get_batch(
    id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(ProductBatch).where(ProductBatch.id == id))
    batch = result.scalars().first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found"
        )
    return batch


@router.patch("/{id}/expiry", response_model=ProductBatchOut)
async def update_batch_expiry(
    id: str,
    payload: ProductBatchExpiryUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    """
    Corrects a data-entry mistake on expiry_date only. Every other field
    on a batch (cost_price, qty_received, qty_remaining, previous_qty) is
    permanently locked once created - see record_batch_movement() in
    app/services/product_batch.py for the only sanctioned way qty changes.
    """
    result = await db.execute(select(ProductBatch).where(ProductBatch.id == id))
    batch = result.scalars().first()

    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found"
        )

    batch.expiry_date = payload.expiry_date
    await db.commit()
    await db.refresh(batch)
    return batch


# No PUT, no general-purpose update, no DELETE.
# A batch is an append-only audit record - it lives for as long as the
# purchase/sale/return history it represents. Quantity changes only ever
# happen through record_batch_movement(), called from inside a
# sale/purchase-return/sales-return transaction, never through this router.
