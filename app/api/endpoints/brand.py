from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db import get_db
from app.schemas.brand import Brand, BrandUpdate, BrandOut
from app.models.brand import Brand as BrandModel
from app.api.deps import require_superadmin_or_admin_or_storekeeper

router = APIRouter(prefix="/brands", tags=["brands"])


@router.post("/", response_model=BrandOut, status_code=status.HTTP_201_CREATED)
async def create_brand(
    brand: Brand,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    new_brand = BrandModel(**brand.model_dump())
    db.add(new_brand)
    await db.commit()
    await db.refresh(new_brand)
    return new_brand


@router.get("/")
async def get_all_brands(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=0, description="Max number of items to return (0 = all)"),
    is_active: bool | None = Query(None, description="Filter by active status (true/false)"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    stmt = select(BrandModel)
    if is_active is not None:
        stmt = stmt.where(BrandModel.is_active == is_active)

    result = await db.execute(stmt)
    query = result.scalars().all()
    total = len(query)
    if limit == 0:
        limit = total

    return {
        "total": total,
        "page": (skip // limit) + 1 if limit else 1,
        "size": limit,
        "items": query[skip: skip + limit],
    }


@router.get("/{id}", response_model=BrandOut)
async def get_brand_by_id(
    id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    result = await db.execute(select(BrandModel).where(BrandModel.id == id))
    brand = result.scalars().first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.put("/{id}", response_model=BrandOut)
async def update_brand(
    id: int,
    brand_update: BrandUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    result = await db.execute(select(BrandModel).where(BrandModel.id == id))
    brand = result.scalars().first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    update_data = brand_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(brand, key, value)

    await db.commit()
    await db.refresh(brand)
    return brand


@router.delete("/{id}")
async def delete_brand(
    id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    result = await db.execute(select(BrandModel).where(BrandModel.id == id))
    brand = result.scalars().first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    await db.delete(brand)
    await db.commit()
    return {"message": "Brand deleted successfully"}
