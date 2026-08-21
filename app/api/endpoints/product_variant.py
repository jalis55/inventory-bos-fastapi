from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.api.deps import require_superadmin_or_admin_or_storekeeper, get_current_user
from app.models.product import Product
from app.models.product_variant import ProductVariant
from app.models.product_batch import ProductBatch
from app.schemas.product_variant import (
    ProductVariantCreate,
    ProductVariantUpdate,
    ProductVariantOut,
    ProductVariantOutPaginate,
)
from app.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func, or_
from decimal import Decimal

# No single router-level prefix - creation is nested under /products,
# everything else is flat under /variants. Both live in this one file
# since they're the same resource.
router = APIRouter(tags=["product-variant"])


async def _stock_map(db: AsyncSession, variant_ids: list[str]) -> dict[str, Decimal]:
    """variant_id -> total qty_remaining across all its batches."""
    if not variant_ids:
        return {}
    rows = (await db.execute(
        select(
            ProductBatch.variant_id,
            func.coalesce(func.sum(ProductBatch.qty_remaining), 0),
        )
        .where(ProductBatch.variant_id.in_(variant_ids))
        .group_by(ProductBatch.variant_id)
    )).all()
    return {r[0]: Decimal(str(r[1])) for r in rows}


async def _with_stock(db: AsyncSession, items: list[ProductVariant]) -> list[ProductVariantOut]:
    """Attach computed `qty_in_stock` while keeping the standard fields."""
    stock = await _stock_map(db, [v.id for v in items])
    return [
        ProductVariantOut.model_validate(v).model_copy(
            update={"qty_in_stock": stock.get(v.id, Decimal("0"))}
        )
        for v in items
    ]


@router.post(
    "/products/{product_id}/variants",
    response_model=ProductVariantOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_variant(
    product_id: str,
    variant: ProductVariantCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    # Confirm the parent product actually exists before creating a variant
    # under it - otherwise you'd get an opaque FK/IntegrityError instead of
    # a clear 404.
    product_result = await db.execute(select(Product).where(Product.id == product_id))
    product = product_result.scalars().first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    try:
        data = variant.model_dump()
        full_name = f"{product.name} {data['variant_name']}"
        new_variant = ProductVariant(product_id=product_id, name=full_name, **data)
        db.add(new_variant)
        await db.commit()
        await db.refresh(new_variant)
        return new_variant
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A variant with this SKU or barcode already exists",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get(
    "/products/{product_id}/variants",
    response_model=ProductVariantOutPaginate,
)
async def list_variants_for_product(
    product_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(ProductVariant).where(ProductVariant.product_id == product_id)
    count_stmt = (
        select(func.count())
        .select_from(ProductVariant)
        .where(ProductVariant.product_id == product_id)
    )

    if is_active is not None:
        stmt = stmt.where(ProductVariant.is_active == is_active)
        count_stmt = count_stmt.where(ProductVariant.is_active == is_active)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    items = await _with_stock(db, list(result.scalars().all()))

    return ProductVariantOutPaginate(
        total=total, page=(skip // limit) + 1, size=len(items), items=items
    )


@router.get("/variants/", response_model=ProductVariantOutPaginate)
async def list_variants(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    product_id: str | None = Query(None, description="Filter by parent product"),
    is_active: bool | None = Query(None),
    search: str | None = Query(
        None, description="Search by SKU, barcode, variant name, or full name"
    ),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(ProductVariant)
    count_stmt = select(func.count()).select_from(ProductVariant)

    if product_id is not None:
        stmt = stmt.where(ProductVariant.product_id == product_id)
        count_stmt = count_stmt.where(ProductVariant.product_id == product_id)

    if is_active is not None:
        stmt = stmt.where(ProductVariant.is_active == is_active)
        count_stmt = count_stmt.where(ProductVariant.is_active == is_active)

    if search:
        term = f"%{search}%"
        search_filter = or_(
            ProductVariant.sku.ilike(term),
            ProductVariant.barcode.ilike(term),
            ProductVariant.variant_name.ilike(term),
            ProductVariant.name.ilike(term),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    items = await _with_stock(db, list(result.scalars().all()))

    return ProductVariantOutPaginate(
        total=total, page=(skip // limit) + 1, size=len(items), items=items
    )


@router.get("/variants/barcode/{barcode}", response_model=ProductVariantOut)
async def get_variant_by_barcode(
    barcode: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    """
    Direct barcode lookup - this is the hot path for POS/checkout scanning,
    so it's a dedicated indexed lookup rather than routing through the
    generic search filter above.
    """
    result = await db.execute(
        select(ProductVariant).where(ProductVariant.barcode == barcode)
    )
    variant = result.scalars().first()

    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No variant found with this barcode",
        )
    return variant


@router.get("/variants/{id}", response_model=ProductVariantOut)
async def get_variant(
    id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == id))
    variant = result.scalars().first()

    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found"
        )
    stock = await _stock_map(db, [variant.id])
    return ProductVariantOut.model_validate(variant).model_copy(
        update={"qty_in_stock": stock.get(variant.id, Decimal("0"))}
    )


@router.put("/variants/{id}", response_model=ProductVariantOut)
async def update_variant(
    id: str,
    variant_update: ProductVariantUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    try:
        result = await db.execute(select(ProductVariant).where(ProductVariant.id == id))
        variant = result.scalars().first()

        if not variant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found"
            )

        update_data = variant_update.model_dump(exclude_unset=True)

        # Keep the denormalized full `name` in sync if variant_name changes.
        if "variant_name" in update_data:
            product_result = await db.execute(
                select(Product).where(Product.id == variant.product_id)
            )
            product = product_result.scalars().first()
            update_data["name"] = f"{product.name} {update_data['variant_name']}"

        for field, value in update_data.items():
            setattr(variant, field, value)

        await db.commit()
        await db.refresh(variant)
        return variant
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A variant with this SKU or barcode already exists",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.patch("/variants/{id}/deactivate", response_model=ProductVariantOut)
async def deactivate_variant(
    id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == id))
    variant = result.scalars().first()

    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found"
        )

    variant.is_active = False
    await db.commit()
    await db.refresh(variant)
    return variant


@router.patch("/variants/{id}/activate", response_model=ProductVariantOut)
async def activate_variant(
    id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == id))
    variant = result.scalars().first()

    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found"
        )

    variant.is_active = True
    await db.commit()
    await db.refresh(variant)
    return variant


# TODO: DELETE /{id} intentionally omitted, same reasoning as the Product
# router - once ProductBatch/StockMovement exist, a variant with any batch
# history must never be hard-deleted (it would orphan cost/stock records).
# Deactivate instead; only allow hard delete after checking zero related
# batches.

# TODO: once ProductBatch exists, add:
#   GET /variants/{id}/stock  -> current stock (SUM of qty_remaining across
#                                 this variant's batches) + reorder_level
#                                 comparison for low-stock flagging.
