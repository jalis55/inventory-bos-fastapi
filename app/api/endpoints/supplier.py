from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.supplier import Supplier
from app.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierOut,
    PaginatedSuppliers,
)
from app.api.deps import get_current_user, require_superadmin_and_admin


router = APIRouter(prefix="/suppliers", tags=["Suppliers"])


@router.get("/", response_model=PaginatedSuppliers)
async def list_suppliers(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    total = (await db.execute(select(func.count()).select_from(Supplier))).scalar_one()

    result = await db.execute(
        select(Supplier)
        .options(selectinload(Supplier.user))
        .order_by(Supplier.id)
        .offset(skip)
        .limit(limit)
    )
    suppliers = result.scalars().all()

    return PaginatedSuppliers(
        total=total,
        skip=skip,
        limit=limit,
        items=suppliers,
    )


@router.get("/{supplier_id}", response_model=SupplierOut)
async def get_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Supplier)
        .options(selectinload(Supplier.user))
        .where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    return supplier


@router.post("/", response_model=SupplierOut, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    supplier_in: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_and_admin),
):
    supplier = Supplier(
        **supplier_in.model_dump(),
        created_by=current_user.id
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)

    # Reload with relationship
    result = await db.execute(
        select(Supplier)
        .options(selectinload(Supplier.user))
        .where(Supplier.id == supplier.id)
    )
    return result.scalar_one()


@router.put("/{supplier_id}", response_model=SupplierOut)
async def update_supplier(
    supplier_id: int,
    supplier_in: SupplierUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    result = await db.execute(
        select(Supplier)
        .options(selectinload(Supplier.user))
        .where(Supplier.id == supplier_id)
    )
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    update_data = supplier_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(supplier, field, value)

    await db.commit()
    await db.refresh(supplier)

    # Reload with relationship
    result = await db.execute(
        select(Supplier)
        .options(selectinload(Supplier.user))
        .where(Supplier.id == supplier.id)
    )
    return result.scalar_one()


@router.delete("/{supplier_id}")
async def delete_supplier(
    supplier_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()

    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    await db.delete(supplier)
    await db.commit()
    return {"message": "Supplier deleted successfully"}