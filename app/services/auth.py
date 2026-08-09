from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.models.user import User
from app.schemas.auth import UserCreate
from app.utils.security import hash_password, verify_password
from app.core.config import settings

async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(select(User).filter(User.email == email))
    return result.scalar_one_or_none()

async def create_user(db: AsyncSession, user_in: UserCreate, current_user: User | None = None) -> User:
    if await get_user_by_email(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Role protection
    if user_in.role not in settings.ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    if current_user is None:
        # First user becomes superadmin (bootstrap)
        role = "superadmin"
    else:
        if current_user.role != "superadmin":
            raise HTTPException(status_code=403, detail="Only superadmin can create users")
        role = user_in.role

    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    user = await get_user_by_email(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    return user