from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.database import get_db
from app.models.user import User
from app.models.product_variant import ProductVariant
from app.schemas.product_variant import (
    ProductVariantCreate,
    ProductVariantUpdate,
    ProductVariantOut,
    PaginatedProductVariants,
)
from app.api.deps import get_current_user, require_superadmin_and_admin


router = APIRouter(prefix="/product-variants", tags=["Product Variants"])


@router.get("/", response_model=PaginatedProductVariants)
async def list_product_variants(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
):
    total = (await db.execute(select(func.count()).select_from(ProductVariant))).scalar_one()
    result = await db.execute(
        select(ProductVariant).order_by(
            ProductVariant.id).offset(skip).limit(limit)
    )
    items = result.scalars().all()
    return PaginatedProductVariants(total=total, skip=skip, limit=limit, items=items)


@router.get("/{variant_id}", response_model=ProductVariantOut)
async def get_product_variant(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(
            status_code=404, detail="Product variant not found")
    return variant


@router.post("/", response_model=ProductVariantOut, status_code=status.HTTP_201_CREATED)
async def create_product_variant(
    variant_in: ProductVariantCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    variant = ProductVariant(**variant_in.model_dump())
    db.add(variant)
    await db.commit()
    await db.refresh(variant)
    return variant


@router.put("/{variant_id}", response_model=ProductVariantOut)
async def update_product_variant(
    variant_id: int,
    variant_in: ProductVariantUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    existing = result.scalar_one_or_none()

    if not existing:
        raise HTTPException(
            status_code=404, detail="Product variant not found")

    update_data = variant_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(existing, field, value)

    await db.commit()
    await db.refresh(existing)
    return existing


@router.delete("/{variant_id}")
async def delete_product_variant(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    result = await db.execute(select(ProductVariant).where(ProductVariant.id == variant_id))
    variant = result.scalar_one_or_none()

    if not variant:
        raise HTTPException(
            status_code=404, detail="Product variant not found")

    await db.delete(variant)
    await db.commit()
    return {"message": "Product variant deleted successfully"}
