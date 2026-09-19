from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.models import Category as CategoryModel
from app.schemas.category import Category, CategoryUpdate, CategoryOut, PaginateResponse
from app.api.deps import get_current_user, require_superadmin_or_admin_or_storekeeper
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/category", tags=["category"])


@router.get("/", response_model=PaginateResponse)
async def list_category(
    skip: int = Query(0, ge=0, description="Number of items to skip"),
    limit: int = Query(10, ge=0, description="Max number of items to return (0 = all)"),
    is_active: bool | None = Query(None, description="Filter by active status (true/false)"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    stmt = select(CategoryModel)
    if is_active is not None:
        stmt = stmt.where(CategoryModel.is_active == is_active)

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


@router.post("/create", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    category: Category,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    try:
        new_category = CategoryModel(**category.model_dump())
        db.add(new_category)
        await db.commit()
        await db.refresh(new_category)
        return new_category
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/{id}", response_model=CategoryOut)
async def update_category(
    id: int,
    category_update: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    result = await db.execute(select(CategoryModel).where(CategoryModel.id == id))
    category = result.scalars().first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    update_data = category_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(category, key, value)

    try:
        await db.commit()
        await db.refresh(category)
        return category
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A category with this name already exists",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.get("/{id}", response_model=CategoryOut)
async def get_category_by_id(
    id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    result = await db.execute(select(CategoryModel).where(CategoryModel.id == id))
    category = result.scalars().first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.delete("/{id}")
async def delete_category(
    id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_superadmin_or_admin_or_storekeeper),
):
    result = await db.execute(select(CategoryModel).where(CategoryModel.id == id))
    category = result.scalars().first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    try:
        await db.delete(category)
        await db.commit()
        return {"message": "Category deleted successfully"}
    except HTTPException:
        raise
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category is referenced by other records and cannot be deleted",
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
