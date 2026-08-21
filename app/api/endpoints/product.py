from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.api.deps import require_superadmin_or_admin_or_storekeeper, get_current_user
from app.models.product import Product
from app.schemas.product import (
    ProductCreate,
    ProductOut,
    ProductUpdate,
    ProductPaginate,
)
from app.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from app.models.product_variant import ProductVariant


router = APIRouter(prefix="/products", tags=["product"])


@router.post("/", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    try:
        dup = await db.execute(
            select(Product.id).where(
                Product.name == product.name,
                Product.brand_id == product.brand_id,
                Product.category_id == product.category_id,
            )
        )
        if dup.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product with this name, brand, and category already exists",
            )

        new_product = Product(**product.model_dump())
        db.add(new_product)
        await db.commit()
        await db.refresh(new_product)

        # Eagerly load the category and brand relationships
        result = await db.execute(
            select(Product)
            .where(Product.id == new_product.id)
            .options(
                selectinload(Product.category),
                selectinload(Product.brand)
            )
        )
        loaded_product = result.scalar_one()

        return loaded_product

    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product with this identifier already exists, or category_id/brand_id is invalid",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/", response_model=ProductPaginate, status_code=status.HTTP_200_OK)
async def list_products(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(
        10, ge=1, le=200, description="Max number of items to return"),
    category_id: int | None = Query(None, description="Filter by category"),
    brand_id: int | None = Query(None, description="Filter by brand"),
    is_active: bool | None = Query(
        None, description="Filter by active status"),
    search: str | None = Query(
        None, description="Search by name or description"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(Product).options(
        selectinload(Product.category),
        selectinload(Product.brand),
    )
    count_stmt = select(func.count()).select_from(Product)

    if is_active is not None:
        stmt = stmt.where(Product.is_active == is_active)
        count_stmt = count_stmt.where(Product.is_active == is_active)

    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
        count_stmt = count_stmt.where(Product.category_id == category_id)

    if brand_id is not None:
        stmt = stmt.where(Product.brand_id == brand_id)
        count_stmt = count_stmt.where(Product.brand_id == brand_id)

    if search:
        term = f"%{search}%"
        search_filter = or_(
            Product.name.ilike(term),
            Product.description.ilike(term),
        )
        stmt = stmt.where(search_filter)
        count_stmt = count_stmt.where(search_filter)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    items = result.scalars().all()

    return ProductPaginate(
        total=total,
        page=(skip // limit) + 1,
        size=len(items),
        items=items,
    )


@router.get("/{id}", response_model=ProductOut, status_code=status.HTTP_200_OK)
async def get_product(
    id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(
        select(Product)
        .where(Product.id == id)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
        )
    )
    product = result.scalars().first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return product


@router.put("/{id}", response_model=ProductOut, status_code=status.HTTP_200_OK)
async def update_product(
    id: str,
    product_update: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    try:
        result = await db.execute(select(Product).where(Product.id == id))
        product = result.scalars().first()

        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
            )

        update_data = product_update.model_dump(exclude_unset=True)
        name_changed = "name" in update_data and update_data["name"] != product.name

        for field, value in update_data.items():
            setattr(product, field, value)

        if name_changed:
            variants_result = await db.execute(
                select(ProductVariant).where(ProductVariant.product_id == id)
            )
            for variant in variants_result.scalars().all():
                variant.name = f"{product.name} {variant.variant_name}"

        dup = await db.execute(
            select(Product.id).where(
                Product.name == product.name,
                Product.brand_id == product.brand_id,
                Product.category_id == product.category_id,
                Product.id != id,
            )
        )
        if dup.scalars().first():
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A product with this name, brand, and category already exists",
            )

        await db.commit()

        # Re-query with relationships so ProductOut can serialize cleanly
        result = await db.execute(
            select(Product)
            .where(Product.id == id)
            .options(
                selectinload(Product.category),
                selectinload(Product.brand),
            )
        )
        return result.scalar_one()

    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid category_id/brand_id or a uniqueness conflict",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.patch("/{id}/deactivate", response_model=ProductOut)
async def deactivate_product(
    id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    result = await db.execute(select(Product).where(Product.id == id))
    product = result.scalars().first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    product.is_active = False
    await db.commit()

    result = await db.execute(
        select(Product)
        .where(Product.id == id)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
        )
    )
    return result.scalar_one()


@router.patch("/{id}/activate", response_model=ProductOut)
async def activate_product(
    id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    result = await db.execute(select(Product).where(Product.id == id))
    product = result.scalars().first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    product.is_active = True
    await db.commit()

    result = await db.execute(
        select(Product)
        .where(Product.id == id)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
        )
    )
    return result.scalar_one()


# NOTE: Hard delete is intentionally not implemented for products.
# Once a product has variants (which can carry batches, stock movements,
# and sales history), deleting it risks destroying data you need for
# auditing. Use PATCH /{id}/deactivate to remove a product from active
# use instead - it's reversible and doesn't touch history.
