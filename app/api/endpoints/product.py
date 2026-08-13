from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.product import Product
from app.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductOutWithRelations,
    PaginatedProducts,
)
from app.api.deps import get_current_user, require_superadmin_and_admin


router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/", response_model=PaginatedProducts)
async def list_products(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="Search by name"),
    is_active: bool | None = Query(None, description="Filter by active status"),
    company_id: int | None = Query(None, description="Filter by company"),
    category_id: int | None = Query(None, description="Filter by category"),
    product_variant_id: int | None = Query(None, description="Filter by variant"),
):
    filters = []
    if search:
        filters.append(Product.name.ilike(f"%{search}%"))
    if is_active is not None:
        filters.append(Product.is_active == is_active)
    if company_id is not None:
        filters.append(Product.company_id == company_id)
    if category_id is not None:
        filters.append(Product.category_id == category_id)
    if product_variant_id is not None:
        filters.append(Product.product_variant_id == product_variant_id)

    total = (
        await db.execute(select(func.count()).select_from(Product).where(*filters))
    ).scalar_one()

    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.company),
            selectinload(Product.category),
            selectinload(Product.product_variant),
        )
        .where(*filters)
        .order_by(Product.id)
        .offset(skip)
        .limit(limit)
    )
    products = result.scalars().all()

    return PaginatedProducts(
        total=total,
        skip=skip,
        limit=limit,
        items=products,
    )


@router.get("/{product_id}", response_model=ProductOutWithRelations)
async def get_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.company),
            selectinload(Product.category),
            selectinload(Product.product_variant),
        )
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@router.post("/", response_model=ProductOutWithRelations, status_code=status.HTTP_201_CREATED)
async def create_product(
    product_in: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    product = Product(**product_in.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)

    # Reload with relationships
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.company),
            selectinload(Product.category),
            selectinload(Product.product_variant),
        )
        .where(Product.id == product.id)
    )
    return result.scalar_one()


@router.put("/{product_id}", response_model=ProductOutWithRelations)
async def update_product(
    product_id: int,
    product_in: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.company),
            selectinload(Product.category),
            selectinload(Product.product_variant),
        )
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    update_data = product_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)

    # Reload again to get updated relationships (if FKs changed)
    result = await db.execute(
        select(Product)
        .options(
            selectinload(Product.company),
            selectinload(Product.category),
            selectinload(Product.product_variant),
        )
        .where(Product.id == product.id)
    )
    return result.scalar_one()


@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    await db.delete(product)
    await db.commit()
    return {"message": "Product deleted successfully"}