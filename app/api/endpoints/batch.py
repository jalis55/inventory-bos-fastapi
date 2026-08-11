from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.models.user import User
from app.models.batch import Batch
from app.schemas.batch import (
    BatchCreate,
    BatchUpdate,
    BatchOut,
    PaginatedBatches,
)
from app.api.deps import get_current_user, require_superadmin_and_admin


router = APIRouter(prefix="/batches", tags=["Batches"])


@router.get("/", response_model=PaginatedBatches)
async def list_batches(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    total = (await db.execute(select(func.count()).select_from(Batch))).scalar_one()

    result = await db.execute(
        select(Batch)
        .options(
            selectinload(Batch.product),
            selectinload(Batch.supplier),
            selectinload(Batch.user),
        )
        .order_by(Batch.id.desc())
        .offset(skip)
        .limit(limit)
    )
    batches = result.scalars().all()

    return PaginatedBatches(total=total, skip=skip, limit=limit, items=batches)


@router.get("/{batch_id}", response_model=BatchOut)
async def get_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Batch)
        .options(
            selectinload(Batch.product),
            selectinload(Batch.supplier),
            selectinload(Batch.user),
        )
        .where(Batch.id == batch_id)
    )
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    return batch


@router.post("/", response_model=BatchOut, status_code=status.HTTP_201_CREATED)
async def create_batch(
    batch_in: BatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_superadmin_and_admin),
):
    # Auto calculate total quantity
    total_quantity = batch_in.received_quantity * batch_in.units_per_package

    batch = Batch(
        **batch_in.model_dump(),
        initial_quantity=total_quantity,
        quantity=total_quantity,
        created_by=current_user.id,
    )

    db.add(batch)
    await db.commit()
    await db.refresh(batch)

    # Reload with relationships
    result = await db.execute(
        select(Batch)
        .options(
            selectinload(Batch.product),
            selectinload(Batch.supplier),
            selectinload(Batch.user),
        )
        .where(Batch.id == batch.id)
    )
    return result.scalar_one()


@router.put("/{batch_id}", response_model=BatchOut)
async def update_batch(
    batch_id: int,
    batch_in: BatchUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    result = await db.execute(
        select(Batch)
        .options(
            selectinload(Batch.product),
            selectinload(Batch.supplier),
            selectinload(Batch.user),
        )
        .where(Batch.id == batch_id)
    )
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    update_data = batch_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(batch, field, value)

    await db.commit()
    await db.refresh(batch)

    result = await db.execute(
        select(Batch)
        .options(
            selectinload(Batch.product),
            selectinload(Batch.supplier),
            selectinload(Batch.user),
        )
        .where(Batch.id == batch.id)
    )
    return result.scalar_one()


@router.delete("/{batch_id}")
async def delete_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_superadmin_and_admin),
):
    result = await db.execute(select(Batch).where(Batch.id == batch_id))
    batch = result.scalar_one_or_none()

    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    await db.delete(batch)
    await db.commit()
    return {"message": "Batch deleted successfully"}