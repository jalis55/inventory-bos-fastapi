from fastapi import APIRouter,Depends,HTTPException,status,Query,Request
from app.db.database import get_db
from app.models.user import User
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryOut, PaginatedCategories
from app.api.deps import get_current_user, require_superadmin_and_admin
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

router=APIRouter(prefix="/categories",tags=["Categories"])


@router.get("/",response_model=PaginatedCategories)
async def list_categories(
    db:AsyncSession=Depends(get_db),
    _:User=Depends(get_current_user),
    skip:int=Query(0,ge=0,description="Number of records to skip"),
    limit:int=Query(20,ge=1,le=100,description="Max records to return"),
):
    total=(await db.execute(select(func.count()).select_from(Category))).scalar_one()
    result=await db.execute(
        select(Category).order_by(Category.id).offset(skip).limit(limit)
    )
    categories=result.scalars().all()
    return PaginatedCategories(total=total,skip=skip,limit=limit,items=categories)


@router.post("/",response_model=CategoryOut)
async def create_category(
    category:CategoryCreate,
    db:AsyncSession=Depends(get_db),
    _:User=Depends(require_superadmin_and_admin),
):
    category=Category(**category.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.get("/{category_id}",response_model=CategoryOut)
async def get_category(
    category_id:int,
    db:AsyncSession=Depends(get_db),
    _:User=Depends(get_current_user),
):
    category=(await db.execute(select(Category).where(Category.id==category_id))).scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404,detail="Category not found")
    return category


@router.put("/{category_id}",response_model=CategoryOut)
async def update_category(
    category_id:int,
    category:CategoryCreate,
    db:AsyncSession=Depends(get_db),
    _:User=Depends(require_superadmin_and_admin),
):
    existing=(await db.execute(select(Category).where(Category.id==category_id))).scalar_one_or_none()
    if not existing:
        raise HTTPException(status_code=404,detail="Category not found")
    existing.name=category.name
    await db.commit()
    await db.refresh(existing)
    return existing

@router.delete("/{category_id}")
async def delete_category(
    category_id:int,
    db:AsyncSession=Depends(get_db),
    _:User=Depends(require_superadmin_and_admin),
):
    category=(await db.execute(select(Category).where(Category.id==category_id))).scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404,detail="Category not found")
    await db.delete(category)
    await db.commit()
    return {"message":"Category deleted successfully"}
