from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from app.db import get_db
from app.core import settings
from app.models import User, Role
from app.schemas.auth import UserOut, UserUpdate, PasswordReset, PaginatedUsers
from app.api.deps import get_current_user, require_superadmin_or_admin, require_admin
from app.utils.security import verify_password, hash_password
from typing import List
from pydantic import EmailStr

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/", response_model=PaginatedUsers)
async def list_users(
    db: AsyncSession = Depends(get_db),
    auth_user: User = Depends(require_superadmin_or_admin),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
):
    total = (await db.execute(select(func.count()).select_from(User))).scalar_one()

    if auth_user.role == Role.SUPER_ADMIN:
        condition = "role != 'super_admin'"
    elif auth_user.role == Role.ADMIN:
        condition = "role != 'admin' AND role != 'super_admin'"
    else:
        condition = "1=1"

    result = await db.execute(
        select(User).where(text(condition)).order_by(User.id).offset(skip).limit(limit)
    )
    users = result.scalars().all()

    return PaginatedUsers(total=total, skip=skip, limit=limit, items=users)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    auth_user: User = Depends(require_superadmin_or_admin),
):
    stmt = select(User).where(User.id == user_id)
    if auth_user.role == Role.ADMIN:
        stmt = stmt.where(User.role.notin_([Role.ADMIN.value, Role.SUPER_ADMIN.value]))

    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/change-password")
async def change_password(
    request_body: PasswordReset,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not verify_password(request_body.old_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid old password")

    current_user.hashed_password = hash_password(request_body.new_password)
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)

    return {"message": "Password changed successfully"}


@router.put("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(User).where(User.id == user_id))
    user_to_update = result.scalar_one_or_none()

    if not user_to_update:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.role not in [Role.SUPER_ADMIN, Role.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admin and admin can update users")

    if user_to_update.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot update your own account")

    if user_to_update.role == Role.SUPER_ADMIN and current_user.role != Role.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only super admin can update super admin users")

    if user_to_update.role == Role.ADMIN and current_user.role == Role.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin cannot update another admin user")

    update_data = user_update.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"] != user_to_update.email:
        email_check = await db.execute(
            select(User).where(User.email == update_data["email"], User.id != user_id)
        )
        if email_check.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered by another user")

    for key, value in update_data.items():
        if value is not None:
            setattr(user_to_update, key, value)

    await db.commit()
    await db.refresh(user_to_update)
    return user_to_update


@router.post("/reset-password")
async def reset_password(
    email: EmailStr,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.role not in [Role.SUPER_ADMIN, Role.ADMIN]:
        raise HTTPException(status_code=403, detail="Permission denied")

    if current_user.role == Role.ADMIN and user.role == Role.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Permission denied")

    if current_user.role == Role.ADMIN and user.role == Role.ADMIN:
        raise HTTPException(status_code=403, detail="Permission denied")

    new_password = settings.DEFAULT_RESET_PASSWORD
    user.hashed_password = hash_password(new_password)
    await db.commit()
    await db.refresh(user)

    return {"message": "Password reset successfully", "new_password": new_password}
